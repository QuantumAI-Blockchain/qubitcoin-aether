"""
Data models for Qubitcoin
Defines core blockchain structures with QVM, Aether Tree, and AIKGS support
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
    # Privacy (Susy Swap) — opt-in confidential transactions
    is_private: bool = False  # True for Susy Swap confidential transactions

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
    quantum_state_root: str = ''
    thought_proof: Optional[dict] = None
    proof_of_thought_hash: str = ''

    def _compute_thought_proof_hash(self) -> str:
        """Derive a compact SHA-256 hash from the thought proof dict."""
        if not self.thought_proof:
            return ''
        tp_bytes = json.dumps(self.thought_proof, sort_keys=True).encode()
        return hashlib.sha256(tp_bytes).hexdigest()

    def calculate_hash(self) -> str:
        # Populate the PoT hash field before hashing the block
        if self.thought_proof and not self.proof_of_thought_hash:
            self.proof_of_thought_hash = self._compute_thought_proof_hash()

        data = {
            'height': self.height,
            'prev_hash': self.prev_hash,
            'proof': self.proof_data,
            'transactions': [tx.txid for tx in self.transactions],
            'timestamp': self.timestamp,
            'difficulty': self.difficulty,
            'state_root': self.state_root,
            'receipts_root': self.receipts_root,
            'quantum_state_root': self.quantum_state_root,
            'thought_proof_hash': self.proof_of_thought_hash,
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
            'quantum_state_root': self.quantum_state_root,
            'thought_proof': self.thought_proof,
            'proof_of_thought_hash': self.proof_of_thought_hash,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Block':
        data = dict(data)  # Don't mutate the original
        data['transactions'] = [
            Transaction.from_dict(tx) for tx in data.get('transactions', [])
        ]
        data.setdefault('state_root', '')
        data.setdefault('receipts_root', '')
        data.setdefault('quantum_state_root', '')
        data.setdefault('thought_proof', None)
        data.setdefault('proof_of_thought_hash', '')
        # Filter to known fields to prevent TypeError on unexpected keys
        known_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in known_fields}
        return cls(**filtered)


@dataclass
class ProofOfSUSY:
    """Proof-of-SUSY-Alignment data structure.

    NOTE: Not instantiated in production code. The consensus engine builds
    proof dicts inline rather than using this dataclass. Retained because
    tests/unit/test_schema_validation.py validates its field structure, and
    it serves as the canonical schema definition for SUSY proofs.
    """
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


# ───────────────────────────────────────────────────────────────────────────
# AIKGS (Aether Incentivized Knowledge Growth System) Models
# Corresponds to sql_new/shared/02_aikgs.sql
# ───────────────────────────────────────────────────────────────────────────

@dataclass
class AIKGSContribution:
    """AIKGS contribution record (aikgs_contributions table)."""
    contribution_id: int
    contributor_address: str
    content_hash: str
    knowledge_node_id: Optional[int] = None
    quality_score: float = 0.0
    novelty_score: float = 0.0
    combined_score: float = 0.0
    tier: str = 'bronze'
    domain: str = 'general'
    reward_amount: Decimal = Decimal(0)
    status: str = 'accepted'
    block_height: int = 0
    created_at: Optional[float] = None

    def to_dict(self) -> dict:
        d = asdict(self)
        d['reward_amount'] = str(d['reward_amount'])
        return d


@dataclass
class AIKGSReward:
    """AIKGS reward distribution (aikgs_rewards table)."""
    contribution_id: int
    contributor_address: str
    amount: Decimal
    base_reward: Decimal
    quality_factor: float
    novelty_factor: float
    tier_multiplier: float
    streak_multiplier: float
    staking_boost: float = 1.0
    early_bonus: float = 1.0
    block_height: int = 0
    created_at: Optional[float] = None

    def to_dict(self) -> dict:
        d = asdict(self)
        d['amount'] = str(d['amount'])
        d['base_reward'] = str(d['base_reward'])
        return d


@dataclass
class AIKGSAffiliate:
    """AIKGS affiliate registration (aikgs_affiliates table)."""
    address: str
    referral_code: str
    referrer_address: Optional[str] = None
    l1_referrals: int = 0
    l2_referrals: int = 0
    total_l1_commission: Decimal = Decimal(0)
    total_l2_commission: Decimal = Decimal(0)
    is_active: bool = True
    created_at: Optional[float] = None

    def to_dict(self) -> dict:
        d = asdict(self)
        d['total_l1_commission'] = str(d['total_l1_commission'])
        d['total_l2_commission'] = str(d['total_l2_commission'])
        return d


@dataclass
class AIKGSCommission:
    """AIKGS commission event (aikgs_commissions table)."""
    affiliate_address: str
    contributor_address: str
    amount: Decimal
    level: int  # 1 or 2
    contribution_id: int
    created_at: Optional[float] = None

    def to_dict(self) -> dict:
        d = asdict(self)
        d['amount'] = str(d['amount'])
        return d


@dataclass
class AIKGSProfile:
    """AIKGS contributor profile (aikgs_profiles table)."""
    address: str
    reputation_points: float = 0.0
    level: int = 1
    level_name: str = 'Novice'
    total_contributions: int = 0
    best_streak: int = 0
    current_streak: int = 0
    gold_count: int = 0
    diamond_count: int = 0
    bounties_fulfilled: int = 0
    referrals: int = 0
    badges: List[str] = field(default_factory=list)
    unlocked_features: List[str] = field(default_factory=lambda: ['basic_chat', 'contribute'])
    last_contribution_at: Optional[float] = None
    updated_at: Optional[float] = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class AIKGSBounty:
    """AIKGS knowledge bounty (aikgs_bounties table)."""
    bounty_id: int
    domain: str
    description: str
    gap_hash: str
    reward_amount: Decimal
    boost_multiplier: float = 1.0
    status: str = 'open'
    claimer_address: Optional[str] = None
    contribution_id: Optional[int] = None
    created_at: Optional[float] = None
    expires_at: Optional[float] = None

    def to_dict(self) -> dict:
        d = asdict(self)
        d['reward_amount'] = str(d['reward_amount'])
        return d


@dataclass
class AIKGSSeason:
    """AIKGS seasonal event (aikgs_seasons table)."""
    season_id: int
    name: str
    domain: str
    boost_multiplier: float
    starts_at: float
    ends_at: float
    active: bool = True

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class AIKGSCurationRound:
    """AIKGS curation round (aikgs_curation_rounds table)."""
    contribution_id: int
    required_votes: int = 3
    votes_for: int = 0
    votes_against: int = 0
    status: str = 'pending'
    finalized_at: Optional[float] = None
    created_at: Optional[float] = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class AIKGSCurationReview:
    """AIKGS curation review (aikgs_curation_reviews table)."""
    contribution_id: int
    curator_address: str
    vote: bool
    comment: Optional[str] = None
    created_at: Optional[float] = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class AIKGSApiKey:
    """AIKGS API key vault entry (aikgs_api_keys table)."""
    key_id: str
    provider: str
    owner_address: str
    encrypted_key: bytes = b''
    model: str = ''
    is_shared: bool = False
    shared_reward_bps: int = 1500
    is_active: bool = True
    use_count: int = 0
    label: str = ''
    created_at: Optional[float] = None
    last_used_at: Optional[float] = None

    def to_dict(self) -> dict:
        d = asdict(self)
        # Don't expose encrypted key in serialization
        d.pop('encrypted_key', None)
        return d
