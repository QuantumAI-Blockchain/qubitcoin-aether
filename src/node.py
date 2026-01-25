import os
import asyncio
import threading
import time
import json
import hashlib
import secrets
from decimal import Decimal, getcontext
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
from collections import defaultdict
import numpy as np

# FastAPI for async RPC
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Database
from sqlalchemy import create_engine, text, pool
from sqlalchemy.orm import sessionmaker, Session as DBSession
from sqlalchemy.exc import IntegrityError, OperationalError

# Quantum computing
from qiskit.quantum_info import SparsePauliOp
from qiskit.circuit.library import TwoLocal
from qiskit_ibm_runtime import QiskitRuntimeService, EstimatorV2, Session as QSession
from qiskit.primitives import StatevectorEstimator
from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager
from qiskit_aer import AerSimulator
from qiskit_aer.noise import NoiseModel

# Cryptography
from dilithium_py.dilithium import Dilithium2

# Utilities
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.status import Status
from scipy.optimize import minimize
import ipfshttpclient
from web3 import Web3
from web3.middleware import geth_poa_middleware

# Logging
import logging
from logging.handlers import RotatingFileHandler

# Set decimal precision for financial calculations
getcontext().prec = 28

# Load environment
load_dotenv()

# Initialize console and logging
console = Console()
logging.basicConfig(
    level=logging.DEBUG if os.getenv('DEBUG', 'false').lower() == 'true' else logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        RotatingFileHandler('qbc_node.log', maxBytes=10485760, backupCount=5),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURATION & CONSTANTS
# ============================================================================

class Config:
    """Centralized configuration management"""
    
    # Node identity
    ADDRESS = os.getenv('ADDRESS')
    PRIVATE_KEY_HEX = os.getenv('PRIVATE_KEY_HEX')
    PUBLIC_KEY_HEX = os.getenv('PUBLIC_KEY_HEX')
    PRIVATE_KEY_ED25519 = os.getenv('PRIVATE_KEY_ED25519')
    
    # Quantum modes
    USE_LOCAL_ESTIMATOR = os.getenv('USE_LOCAL_ESTIMATOR', 'true').lower() == 'true'
    USE_SIMULATOR = os.getenv('USE_SIMULATOR', 'false').lower() == 'true'
    IBM_TOKEN = os.getenv('IBM_TOKEN')
    IBM_INSTANCE = os.getenv('IBM_INSTANCE')
    
    # Network
    P2P_PORT = int(os.getenv('P2P_PORT', 4001))
    PEER_SEEDS = json.loads(os.getenv('PEER_SEEDS', '[]'))
    RPC_PORT = int(os.getenv('RPC_PORT', 5000))
    
    # Database
    DATABASE_URL = os.getenv('DATABASE_URL')
    
    # IPFS
    IPFS_API = os.getenv('IPFS_API', '/ip4/127.0.0.1/tcp/5001/http')
    PINATA_JWT = os.getenv('PINATA_JWT')
    
    # Bridge
    INFURA_URL = os.getenv('INFURA_URL')
    ETH_PRIVATE_KEY = os.getenv('ETH_PRIVATE_KEY')
    BRIDGE_CONTRACT_ADDRESS = os.getenv('BRIDGE_CONTRACT_ADDRESS', '0x0000000000000000000000000000000000000000')
    
    # Protocol constants
    MAX_SUPPLY = Decimal('21000000')
    INITIAL_REWARD = Decimal('50')
    HALVING_INTERVAL = 210000
    MIN_FEE = Decimal('0.01')
    FEE_RATE = Decimal('0.001')
    INITIAL_DIFFICULTY = 0.5
    TARGET_BLOCK_TIME = 600  # 10 minutes
    DIFFICULTY_ADJUSTMENT_INTERVAL = 2016  # Blocks
    MINING_INTERVAL = int(os.getenv('MINING_INTERVAL', 10))
    SNAPSHOT_INTERVAL = int(os.getenv('SNAPSHOT_INTERVAL', 10))
    
    # VQE parameters
    VQE_REPS = 1
    VQE_MAXITER = 100
    VQE_TOLERANCE = 1e-6
    ENERGY_VALIDATION_TOLERANCE = 1e-3
    
    # P2P parameters
    MAX_PEERS = 50
    PEER_TIMEOUT = 300
    MESSAGE_CACHE_SIZE = 10000
    GOSSIP_RATE_LIMIT = 100  # Messages per second
    
    # Consensus
    CONFIRMATION_DEPTH = 6
    MAX_REORG_DEPTH = 100
    
    @classmethod
    def validate(cls):
        """Validate critical configuration"""
        required = ['ADDRESS', 'PRIVATE_KEY_HEX', 'PUBLIC_KEY_HEX', 'DATABASE_URL']
        missing = [k for k in required if not getattr(cls, k)]
        if missing:
            raise ValueError(f"Missing required config: {', '.join(missing)}")

Config.validate()

# ============================================================================
# DATA MODELS
# ============================================================================

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
    
    def to_dict(self) -> dict:
        return asdict(self)

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
        """Calculate transaction ID from inputs/outputs"""
        data = {
            'inputs': self.inputs,
            'outputs': self.outputs,
            'fee': str(self.fee),
            'timestamp': self.timestamp
        }
        return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()
    
    def to_dict(self) -> dict:
        d = asdict(self)
        d['fee'] = str(d['fee'])
        d['outputs'] = [{'address': o['address'], 'amount': str(o['amount'])} for o in d['outputs']]
        return d

@dataclass
class Block:
    """Block with quantum proof"""
    height: int
    prev_hash: str
    proof_data: dict
    transactions: List[Transaction]
    timestamp: float
    difficulty: float
    
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
        return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()

# ============================================================================
# DATABASE LAYER
# ============================================================================

class DatabaseManager:
    """Thread-safe database operations with connection pooling"""
    
    def __init__(self):
        self.engine = create_engine(
            Config.DATABASE_URL,
            poolclass=pool.QueuePool,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
            pool_recycle=3600
        )
        self.SessionLocal = sessionmaker(bind=self.engine)
        self._local = threading.local()
    
    def get_session(self) -> DBSession:
        """Get thread-local database session"""
        if not hasattr(self._local, 'session'):
            self._local.session = self.SessionLocal()
        return self._local.session
    
    def execute_with_retry(self, func, max_retries=3):
        """Execute database operation with retry logic"""
        for attempt in range(max_retries):
            try:
                return func()
            except OperationalError as e:
                if attempt == max_retries - 1:
                    raise
                logger.warning(f"DB operation failed (attempt {attempt + 1}): {e}")
                time.sleep(2 ** attempt)
    
    def get_utxos(self, address: str) -> List[UTXO]:
        """Get all unspent outputs for address"""
        session = self.get_session()
        result = session.execute(
            text("""
                SELECT txid, vout, amount, address, proof, block_height, spent
                FROM utxos
                WHERE address = :addr AND spent = false
                ORDER BY block_height DESC
            """),
            {'addr': address}
        )
        return [UTXO(**dict(row)) for row in result]
    
    def mark_utxos_spent(self, inputs: List[dict], session: DBSession):
        """Mark UTXOs as spent atomically"""
        for inp in inputs:
            session.execute(
                text("""
                    UPDATE utxos 
                    SET spent = true 
                    WHERE txid = :txid AND vout = :vout AND spent = false
                """),
                {'txid': inp['txid'], 'vout': inp['vout']}
            )
    
    def create_utxos(self, txid: str, outputs: List[dict], block_height: int, proof: dict, session: DBSession):
        """Create new UTXOs from transaction outputs"""
        for vout, output in enumerate(outputs):
            session.execute(
                text("""
                    INSERT INTO utxos (txid, vout, amount, address, proof, block_height, spent)
                    VALUES (:txid, :vout, :amount, :address, :proof, :block_height, false)
                """),
                {
                    'txid': txid,
                    'vout': vout,
                    'amount': str(output['amount']),
                    'address': output['address'],
                    'proof': json.dumps(proof),
                    'block_height': block_height
                }
            )
    
    def get_balance(self, address: str) -> Decimal:
        """Calculate balance from UTXOs"""
        utxos = self.get_utxos(address)
        return sum(utxo.amount for utxo in utxos)
    
    def get_current_height(self) -> int:
        """Get current blockchain height"""
        session = self.get_session()
        result = session.execute(text("SELECT COALESCE(MAX(height), -1) FROM blocks"))
        return result.scalar()
    
    def get_block(self, height: int) -> Optional[Block]:
        """Get block by height"""
        session = self.get_session()
        result = session.execute(
            text("SELECT * FROM blocks WHERE height = :h"),
            {'h': height}
        ).fetchone()
        
        if not result:
            return None
        
        # Reconstruct block with transactions
        block_data = dict(result)
        tx_results = session.execute(
            text("SELECT * FROM transactions WHERE block_height = :h"),
            {'h': height}
        )
        
        transactions = []
        for tx_row in tx_results:
            tx_data = dict(tx_row)
            transactions.append(Transaction(
                txid=tx_data['txid'],
                inputs=json.loads(tx_data['inputs']),
                outputs=json.loads(tx_data['outputs']),
                fee=Decimal(tx_data['fee']),
                signature=tx_data['signature'],
                public_key=tx_data['public_key'],
                timestamp=tx_data['timestamp'],
                block_height=height,
                status=tx_data['status']
            ))
        
        return Block(
            height=block_data['height'],
            prev_hash=block_data['prev_hash'],
            proof_data=json.loads(block_data['proof_json']),
            transactions=transactions,
            timestamp=block_data['created_at'].timestamp(),
            difficulty=block_data['difficulty']
        )
    
    def store_block(self, block: Block, session: DBSession):
        """Store block and update UTXOs atomically"""
        # Insert block
        session.execute(
            text("""
                INSERT INTO blocks (height, prev_hash, proof_json, difficulty, created_at)
                VALUES (:h, :ph, :pj, :d, to_timestamp(:ts))
            """),
            {
                'h': block.height,
                'ph': block.prev_hash,
                'pj': json.dumps(block.proof_data),
                'd': block.difficulty,
                'ts': block.timestamp
            }
        )
        
        # Process each transaction
        for tx in block.transactions:
            # Mark inputs as spent
            self.mark_utxos_spent(tx.inputs, session)
            
            # Create new UTXOs from outputs
            self.create_utxos(tx.txid, tx.outputs, block.height, block.proof_data, session)
            
            # Update transaction status
            session.execute(
                text("""
                    UPDATE transactions 
                    SET status = 'confirmed', block_height = :bh
                    WHERE txid = :txid
                """),
                {'bh': block.height, 'txid': tx.txid}
            )
        
        # Update total supply
        total_reward = sum(Decimal(o['amount']) for tx in block.transactions for o in tx.outputs 
                          if tx.inputs == [])  # Coinbase transactions
        session.execute(
            text("UPDATE supply SET total_minted = total_minted + :r"),
            {'r': str(total_reward)}
        )
        
        session.commit()
    
    def get_pending_transactions(self, limit: int = 1000) -> List[Transaction]:
        """Get pending transactions ordered by fee rate"""
        session = self.get_session()
        results = session.execute(
            text("""
                SELECT * FROM transactions 
                WHERE status = 'pending'
                ORDER BY CAST(fee AS DECIMAL) DESC
                LIMIT :limit
            """),
            {'limit': limit}
        )
        
        transactions = []
        for row in results:
            tx_data = dict(row)
            transactions.append(Transaction(
                txid=tx_data['txid'],
                inputs=json.loads(tx_data['inputs']),
                outputs=json.loads(tx_data['outputs']),
                fee=Decimal(tx_data['fee']),
                signature=tx_data['signature'],
                public_key=tx_data['public_key'],
                timestamp=tx_data['timestamp'],
                status=tx_data['status']
            ))
        
        return transactions
    
    def get_difficulty_at_height(self, height: int) -> float:
        """Get difficulty at specific height"""
        session = self.get_session()
        result = session.execute(
            text("SELECT difficulty FROM blocks WHERE height = :h"),
            {'h': height}
        )
        row = result.fetchone()
        return row[0] if row else Config.INITIAL_DIFFICULTY

db = DatabaseManager()

# ============================================================================
# QUANTUM LAYER
# ============================================================================

class QuantumEngine:
    """VQE-based Proof-of-SUSY-Alignment engine"""
    
    def __init__(self):
        self.estimator = None
        self.backend = None
        self.service = None
        self.noise_model = None
        
        self._initialize_backend()
    
    def _initialize_backend(self):
        """Initialize quantum backend based on configuration"""
        if Config.USE_LOCAL_ESTIMATOR:
            self.estimator = StatevectorEstimator()
            logger.info("Quantum mode: Local StatevectorEstimator (exact)")
        elif Config.USE_SIMULATOR:
            # Noisy simulator with realistic noise model
            self.backend = AerSimulator()
            self.noise_model = NoiseModel.from_backend(self.backend)
            self.estimator = StatevectorEstimator()
            logger.info("Quantum mode: Noisy AerSimulator")
        else:
            # Real IBM Quantum hardware
            try:
                self.service = QiskitRuntimeService(
                    channel="ibm_quantum",
                    token=Config.IBM_TOKEN,
                    instance=Config.IBM_INSTANCE
                )
                self.backend = self.service.least_busy(
                    operational=True,
                    simulator=False,
                    min_num_qubits=5
                )
                self.estimator = EstimatorV2
                logger.info(f"Quantum mode: IBM Quantum ({self.backend.name})")
            except Exception as e:
                logger.error(f"Failed to connect to IBM Quantum: {e}")
                logger.info("Falling back to local estimator")
                self.estimator = StatevectorEstimator()
    
    def generate_hamiltonian(self, num_qubits: int = 4, seed: Optional[int] = None) -> List[Tuple[float, str]]:
        """Generate random SUSY Hamiltonian"""
        if seed:
            np.random.seed(seed)
        
        # Generate Pauli strings with balanced coefficients
        num_terms = num_qubits + 1
        paulis = []
        coeffs = []
        
        for _ in range(num_terms):
            pauli_str = ''.join(np.random.choice(['I', 'X', 'Y', 'Z'], num_qubits))
            coeff = np.random.uniform(-1, 1)
            paulis.append(pauli_str)
            coeffs.append(coeff)
        
        return list(zip(coeffs, paulis))
    
    def create_ansatz(self, num_qubits: int = 4, reps: int = None) -> TwoLocal:
        """Create parameterized quantum circuit"""
        reps = reps or Config.VQE_REPS
        return TwoLocal(
            num_qubits,
            rotation_blocks='ry',
            entanglement_blocks='cz',
            entanglement='linear',
            reps=reps,
            insert_barriers=True
        )
    
    def compute_energy(self, params: np.ndarray, hamiltonian: List[Tuple[float, str]], 
                      num_qubits: int = 4) -> float:
        """Compute expectation value using VQE"""
        ansatz = self.create_ansatz(num_qubits)
        bound_circuit = ansatz.assign_parameters(params)
        observable = SparsePauliOp.from_list(hamiltonian)
        
        # Retry logic for IBM quota/network issues
        max_retries = 3
        for attempt in range(max_retries):
            try:
                if self.backend and not Config.USE_LOCAL_ESTIMATOR:
                    # Transpile for real hardware
                    pm = generate_preset_pass_manager(
                        optimization_level=2,
                        target=self.backend.target
                    )
                    isa_circuit = pm.run(bound_circuit)
                    isa_observable = observable.apply_layout(isa_circuit.layout)
                    
                    with QSession(service=self.service, backend=self.backend) as session:
                        job = self.estimator.run(pubs=[(isa_circuit, [isa_observable])])
                        result = job.result()[0]
                        return float(result.data.evs)
                else:
                    # Local simulation
                    pub = (bound_circuit, [observable])
                    result = self.estimator.run(pubs=[pub]).result()[0]
                    return float(result.data.evs)
                    
            except Exception as e:
                if 'quota' in str(e).lower() or 'busy' in str(e).lower():
                    if attempt < max_retries - 1:
                        wait_time = 60 * (2 ** attempt)
                        logger.warning(f"IBM quota exceeded, retry {attempt + 1}/{max_retries} in {wait_time}s")
                        time.sleep(wait_time)
                    else:
                        raise RuntimeError("IBM quota exhausted after retries")
                else:
                    raise
        
        raise RuntimeError("VQE computation failed")
    
    def optimize_vqe(self, hamiltonian: List[Tuple[float, str]], 
                    initial_params: Optional[np.ndarray] = None) -> Tuple[np.ndarray, float]:
        """Run VQE optimization to find ground state"""
        num_qubits = len(hamiltonian[0][1])
        ansatz = self.create_ansatz(num_qubits)
        
        if initial_params is None:
            initial_params = np.random.uniform(0, 2 * np.pi, ansatz.num_parameters)
        
        # Define objective function
        def objective(params):
            return self.compute_energy(params, hamiltonian, num_qubits)
        
        # Optimize using COBYLA
        result = minimize(
            objective,
            initial_params,
            method='COBYLA',
            options={
                'maxiter': Config.VQE_MAXITER,
                'tol': Config.VQE_TOLERANCE,
                'rhobeg': 0.1
            }
        )
        
        return result.x, result.fun
    
    def validate_proof(self, params: np.ndarray, hamiltonian: List[Tuple[float, str]], 
                      claimed_energy: float, difficulty: float) -> Tuple[bool, str]:
        """Validate a quantum proof"""
        try:
            # Recompute energy
            computed_energy = self.compute_energy(params, hamiltonian)
            
            # Check energy matches claim within tolerance
            energy_diff = abs(computed_energy - claimed_energy)
            if energy_diff > Config.ENERGY_VALIDATION_TOLERANCE:
                return False, f"Energy mismatch: {energy_diff:.6f} > {Config.ENERGY_VALIDATION_TOLERANCE}"
            
            # Check meets difficulty
            if computed_energy >= difficulty:
                return False, f"Energy {computed_energy:.6f} >= difficulty {difficulty:.6f}"
            
            return True, "Valid"
            
        except Exception as e:
            return False, f"Validation error: {str(e)}"

quantum_engine = QuantumEngine()

# ============================================================================
# CRYPTOGRAPHY LAYER
# ============================================================================

class CryptoManager:
    """Post-quantum cryptography operations"""
    
    @staticmethod
    def generate_keypair() -> Tuple[bytes, bytes]:
        """Generate Dilithium2 keypair"""
        return Dilithium2.keygen()
    
    @staticmethod
    def sign(private_key: bytes, message: bytes) -> bytes:
        """Sign message with Dilithium2"""
        return Dilithium2.sign(private_key, message)
    
    @staticmethod
    def verify(public_key: bytes, message: bytes, signature: bytes) -> bool:
        """Verify Dilithium2 signature"""
        try:
            return Dilithium2.verify(public_key, message, signature)
        except Exception as e:
            logger.warning(f"Signature verification failed: {e}")
            return False
    
    @staticmethod
    def derive_address(public_key: bytes) -> str:
        """Derive address from public key"""
        return hashlib.sha256(public_key).hexdigest()[:40]
    
    @staticmethod
    def sign_transaction(tx: Transaction, private_key: bytes) -> str:
        """Sign transaction"""
        # Create canonical message from transaction
        message = json.dumps({
            'inputs': tx.inputs,
            'outputs': [{'address': o['address'], 'amount': str(o['amount'])} for o in tx.outputs],
            'fee': str(tx.fee),
            'timestamp': tx.timestamp
        }, sort_keys=True).encode()
        
        signature = CryptoManager.sign(private_key, message)
        return signature.hex()
    
    @staticmethod
    def verify_transaction(tx: Transaction) -> bool:
        """Verify transaction signature"""
        try:
            message = json.dumps({
                'inputs': tx.inputs,
                'outputs': [{'address': o['address'], 'amount': str(o['amount'])} for o in tx.outputs],
                'fee': str(tx.fee),
                'timestamp': tx.timestamp
            }, sort_keys=True).encode()
            
            public_key = bytes.fromhex(tx.public_key)
            signature = bytes.fromhex(tx.signature)
            
            return CryptoManager.verify(public_key, message, signature)
        except Exception as e:
            logger.error(f"Transaction verification error: {e}")
            return False

crypto = CryptoManager()

# ============================================================================
# CONSENSUS LAYER
# ============================================================================

class ConsensusEngine:
    """Proof-of-SUSY-Alignment consensus with dynamic difficulty"""
    
    def __init__(self):
        self.difficulty_cache = {}
    
    def calculate_reward(self, height: int) -> Decimal:
        """Calculate block reward with halvings"""
        halvings = height // Config.HALVING_INTERVAL
        base_reward = Config.INITIAL_REWARD / (2 ** halvings)
        
        # Ensure we don't exceed max supply
        session = db.get_session()
        result = session.execute(text("SELECT total_minted FROM supply"))
        total_minted = Decimal(result.scalar() or 0)
        
        remaining = Config.MAX_SUPPLY - total_minted
        return min(base_reward, remaining)
    
    def calculate_difficulty(self, height: int) -> float:
        """Calculate difficulty with adjustment every DIFFICULTY_ADJUSTMENT_INTERVAL"""
        if height < Config.DIFFICULTY_ADJUSTMENT_INTERVAL:
            return Config.INITIAL_DIFFICULTY
        
        # Check cache
        adjustment_height = (height // Config.DIFFICULTY_ADJUSTMENT_INTERVAL) * Config.DIFFICULTY_ADJUSTMENT_INTERVAL
        if adjustment_height in self.difficulty_cache:
            return self.difficulty_cache[adjustment_height]
        
        # Get last adjustment block time
        session = db.get_session()
        result = session.execute(
            text("""
                SELECT created_at FROM blocks 
                WHERE height = :h
            """),
            {'h': adjustment_height - Config.DIFFICULTY_ADJUSTMENT_INTERVAL}
        )
        prev_adjustment_time = result.scalar()
        
        result = session.execute(
            text("SELECT created_at FROM blocks WHERE height = :h"),
            {'h': adjustment_height - 1}
        )
        last_block_time = result.scalar()
        
        if not prev_adjustment_time or not last_block_time:
            return Config.INITIAL_DIFFICULTY
        
        # Calculate actual time taken
        actual_time = (last_block_time - prev_adjustment_time).total_seconds()
        expected_time = Config.TARGET_BLOCK_TIME * Config.DIFFICULTY_ADJUSTMENT_INTERVAL
        
        # Get previous difficulty
        prev_difficulty = db.get_difficulty_at_height(adjustment_height - 1)
        
        # Adjust difficulty (limit change to 4x up or down)
        ratio = expected_time / actual_time
        ratio = max(0.25, min(4.0, ratio))
        
        new_difficulty = prev_difficulty * ratio
        new_difficulty = max(0.1, min(1.0, new_difficulty))  # Clamp between 0.1 and 1.0
        
        self.difficulty_cache[adjustment_height] = new_difficulty
        logger.info(f"Difficulty adjusted at height {height}: {prev_difficulty:.4f} -> {new_difficulty:.4f} (ratio: {ratio:.2f})")
        
        return new_difficulty
    
    def validate_block(self, block: Block, prev_block: Optional[Block] = None) -> Tuple[bool, str]:
        """Comprehensive block validation"""
        try:
            # Validate height sequence
            expected_height = (prev_block.height + 1) if prev_block else 0
            if block.height != expected_height:
                return False, f"Invalid height: {block.height} != {expected_height}"
            
            # Validate prev_hash
            expected_prev_hash = prev_block.calculate_hash() if prev_block else '0' * 64
            if block.prev_hash != expected_prev_hash:
                return False, f"Invalid prev_hash"
            
            # Validate difficulty
            expected_difficulty = self.calculate_difficulty(block.height)
            if abs(block.difficulty - expected_difficulty) > 0.001:
                return False, f"Invalid difficulty: {block.difficulty} != {expected_difficulty}"
            
            # Validate quantum proof
            proof = block.proof_data
            valid, reason = quantum_engine.validate_proof(
                np.array(proof['params']),
                proof['challenge'],
                proof['energy'],
                block.difficulty
            )
            if not valid:
                return False, f"Invalid quantum proof: {reason}"
            
            # Validate proof signature
            pk = bytes.fromhex(proof['public_key'])
            msg = str(proof['params']).encode()
            sig = bytes.fromhex(proof['signature'])
            if not crypto.verify(pk, msg, sig):
                return False, "Invalid proof signature"
            
            # Validate transactions
            total_fees = Decimal(0)
            coinbase_count = 0
            
            for tx in block.transactions:
                # Check for coinbase (mining reward)
                if len(tx.inputs) == 0:
                    coinbase_count += 1
                    if coinbase_count > 1:
                        return False, "Multiple coinbase transactions"
                    
                    # Validate coinbase amount
                    expected_reward = self.calculate_reward(block.height)
                    coinbase_amount = sum(Decimal(o['amount']) for o in tx.outputs)
                    if coinbase_amount > expected_reward + total_fees:
                        return False, f"Excessive coinbase: {coinbase_amount} > {expected_reward + total_fees}"
                    continue
                
                # Validate regular transaction
                if not crypto.verify_transaction(tx):
                    return False, f"Invalid transaction signature: {tx.txid}"
                
                # Verify inputs exist and calculate input total
                input_total = Decimal(0)
                session = db.get_session()
                for inp in tx.inputs:
                    utxo_result = session.execute(
                        text("SELECT amount, spent FROM utxos WHERE txid=:t AND vout=:v"),
                        {'t': inp['txid'], 'v': inp['vout']}
                    ).fetchone()
                    
                    if not utxo_result:
                        return False, f"Input UTXO not found: {inp['txid']}:{inp['vout']}"
                    
                    if utxo_result[1]:  # spent
                        return False, f"Double spend detected: {inp['txid']}:{inp['vout']}"
                    
                    input_total += Decimal(utxo_result[0])
                
                # Calculate output total
                output_total = sum(Decimal(o['amount']) for o in tx.outputs)
                
                # Verify fee
                calculated_fee = input_total - output_total
                if calculated_fee < 0:
                    return False, f"Negative fee in transaction: {tx.txid}"
                
                if abs(calculated_fee - tx.fee) > Decimal('0.00000001'):
                    return False, f"Fee mismatch: {calculated_fee} != {tx.fee}"
                
                total_fees += tx.fee
            
            # Ensure coinbase exists
            if coinbase_count == 0:
                return False, "No coinbase transaction"
            
            # Validate timestamp (not too far in future)
            if block.timestamp > time.time() + 7200:  # 2 hours
                return False, "Block timestamp too far in future"
            
            return True, "Valid"
            
        except Exception as e:
            logger.error(f"Block validation error: {e}")
            return False, f"Validation exception: {str(e)}"
    
    def validate_fork_chain(self, blocks: List[Block]) -> bool:
        """Validate entire fork chain before reorganization"""
        for i, block in enumerate(blocks):
            prev = blocks[i-1] if i > 0 else db.get_block(block.height - 1)
            valid, reason = self.validate_block(block, prev)
            if not valid:
                logger.error(f"Fork block {block.height} invalid: {reason}")
                return False
        return True

consensus = ConsensusEngine()

# ============================================================================
# P2P NETWORK LAYER
# ============================================================================

class PeerReputation:
    """Peer reputation and rate limiting system"""
    
    def __init__(self):
        self.scores = defaultdict(lambda: 100)
        self.message_counts = defaultdict(lambda: defaultdict(list))
        self.banned_peers = set()
    
    def record_message(self, peer_id: str, topic: str) -> bool:
        """Record message and enforce rate limits"""
        if peer_id in self.banned_peers:
            return False
        
        now = time.time()
        self.message_counts[peer_id][topic].append(now)
        
        # Clean old messages (older than 1 second)
        self.message_counts[peer_id][topic] = [
            t for t in self.message_counts[peer_id][topic] if now - t < 1.0
        ]
        
        # Check rate limit
        if len(self.message_counts[peer_id][topic]) > Config.GOSSIP_RATE_LIMIT:
            self.penalize(peer_id, 5, f"Rate limit exceeded on {topic}")
            return False
        
        return True
    
    def reward(self, peer_id: str, amount: int = 1):
        """Reward peer for good behavior"""
        self.scores[peer_id] = min(100, self.scores[peer_id] + amount)
    
    def penalize(self, peer_id: str, amount: int, reason: str = ""):
        """Penalize peer for bad behavior"""
        self.scores[peer_id] = max(0, self.scores[peer_id] - amount)
        logger.warning(f"Penalized peer {peer_id[:8]} by {amount} (reason: {reason}), score: {self.scores[peer_id]}")
        
        if self.scores[peer_id] <= 10:
            self.banned_peers.add(peer_id)
            logger.warning(f"Banned peer {peer_id[:8]} due to low reputation")
    
    def is_trusted(self, peer_id: str) -> bool:
        """Check if peer is trusted"""
        return self.scores[peer_id] >= 50 and peer_id not in self.banned_peers

class P2PNetwork:
    """libp2p-based P2P network manager"""
    
    def __init__(self):
        self.node = None
        self.peer_id = None
        self.reputation = PeerReputation()
        self.message_cache = set()
        self.cache_lock = threading.Lock()
        
    def initialize(self):
        """Initialize libp2p node"""
        try:
            # Import libp2p bindings (assuming Rust FFI)
            from qbc_p2p import Libp2pNode
            
            # Use ed25519 key from config or generate
            if Config.PRIVATE_KEY_ED25519:
                sk_bytes = bytes.fromhex(Config.PRIVATE_KEY_ED25519)
            else:
                sk_bytes = secrets.token_bytes(32)
                logger.warning("Generated new P2P key - add to .env for persistence")
            
            self.node = Libp2pNode(sk_bytes)
            self.peer_id = self.node.peer_id()
            
            # Start listening
            listen_addr = f"/ip4/0.0.0.0/tcp/{Config.P2P_PORT}"
            self.node.listen(listen_addr)
            
            # Bootstrap from seed peers
            if Config.PEER_SEEDS:
                self.node.bootstrap(Config.PEER_SEEDS)
                logger.info(f"Bootstrapping with {len(Config.PEER_SEEDS)} seed peers")
            
            # Subscribe to topics
            topics = [
                '/qbc/blocks',
                '/qbc/transactions',
                '/qbc/snapshots',
                '/qbc/swaps',
                '/qbc/bridge'
            ]
            
            for topic in topics:
                self.node.subscribe(topic)
            
            logger.info(f"P2P node initialized: {self.peer_id[:16]}... listening on {listen_addr}")
            
        except ImportError:
            logger.error("libp2p bindings not available, P2P disabled")
            self.node = None
        except Exception as e:
            logger.error(f"P2P initialization failed: {e}")
            self.node = None
    
    def publish(self, topic: str, data: dict):
        """Publish message to topic"""
        if not self.node:
            return
        
        try:
            message = json.dumps(data).encode()
            self.node.publish(topic, message)
        except Exception as e:
            logger.error(f"Failed to publish to {topic}: {e}")
    
    def is_duplicate(self, message_hash: str) -> bool:
        """Check if message already processed"""
        with self.cache_lock:
            if message_hash in self.message_cache:
                return True
            
            self.message_cache.add(message_hash)
            
            # Limit cache size
            if len(self.message_cache) > Config.MESSAGE_CACHE_SIZE:
                # Remove oldest (approximate FIFO)
                self.message_cache.pop()
            
            return False
    
    def handle_block_message(self, data: dict, peer_id: str):
        """Handle received block"""
        try:
            # Check rate limit
            if not self.reputation.record_message(peer_id, '/qbc/blocks'):
                return
            
            # Reconstruct block
            block = Block(
                height=data['height'],
                prev_hash=data['prev_hash'],
                proof_data=data['proof_data'],
                transactions=[Transaction(**tx) for tx in data['transactions']],
                timestamp=data['timestamp'],
                difficulty=data['difficulty']
            )
            
            # Check if duplicate
            block_hash = block.calculate_hash()
            if self.is_duplicate(block_hash):
                return
            
            # Validate block
            current_height = db.get_current_height()
            
            if block.height <= current_height:
                # Might be a fork
                asyncio.create_task(self.handle_fork(block, peer_id))
            elif block.height == current_height + 1:
                # Next block in chain
                prev_block = db.get_block(current_height)
                valid, reason = consensus.validate_block(block, prev_block)
                
                if valid:
                    # Append to chain
                    asyncio.create_task(self.append_block(block))
                    self.reputation.reward(peer_id, 2)
                else:
                    logger.warning(f"Invalid block from peer {peer_id[:8]}: {reason}")
                    self.reputation.penalize(peer_id, 10, reason)
            else:
                # Future block - might need to sync
                logger.info(f"Received future block {block.height} (current: {current_height})")
                asyncio.create_task(self.request_sync(peer_id, current_height + 1, block.height))
                
        except Exception as e:
            logger.error(f"Error handling block message: {e}")
            self.reputation.penalize(peer_id, 5, "Invalid block format")
    
    def handle_transaction_message(self, data: dict, peer_id: str):
        """Handle received transaction"""
        try:
            if not self.reputation.record_message(peer_id, '/qbc/transactions'):
                return
            
            tx = Transaction(**data)
            
            # Check duplicate
            if self.is_duplicate(tx.txid):
                return
            
            # Validate transaction
            if not crypto.verify_transaction(tx):
                self.reputation.penalize(peer_id, 3, "Invalid transaction signature")
                return
            
            # Verify inputs exist
            session = db.get_session()
            input_total = Decimal(0)
            
            for inp in tx.inputs:
                utxo = session.execute(
                    text("SELECT amount, spent FROM utxos WHERE txid=:t AND vout=:v"),
                    {'t': inp['txid'], 'v': inp['vout']}
                ).fetchone()
                
                if not utxo or utxo[1]:
                    self.reputation.penalize(peer_id, 2, "Invalid UTXO reference")
                    return
                
                input_total += Decimal(utxo[0])
            
            output_total = sum(Decimal(o['amount']) for o in tx.outputs)
            
            if input_total < output_total + tx.fee:
                self.reputation.penalize(peer_id, 2, "Insufficient inputs")
                return
            
            # Add to mempool
            try:
                session.execute(
                    text("""
                        INSERT INTO transactions 
                        (txid, inputs, outputs, fee, signature, public_key, timestamp, status)
                        VALUES (:txid, :inputs, :outputs, :fee, :sig, :pk, :ts, 'pending')
                    """),
                    {
                        'txid': tx.txid,
                        'inputs': json.dumps(tx.inputs),
                        'outputs': json.dumps(tx.outputs),
                        'fee': str(tx.fee),
                        'sig': tx.signature,
                        'pk': tx.public_key,
                        'ts': tx.timestamp
                    }
                )
                session.commit()
                
                self.reputation.reward(peer_id, 1)
                logger.debug(f"Added transaction {tx.txid[:8]} to mempool")
                
            except IntegrityError:
                # Already in mempool
                pass
                
        except Exception as e:
            logger.error(f"Error handling transaction: {e}")
            self.reputation.penalize(peer_id, 2, "Transaction processing error")
    
    def handle_snapshot_message(self, data: dict, peer_id: str):
        """Handle IPFS snapshot announcement"""
        try:
            if not self.reputation.record_message(peer_id, '/qbc/snapshots'):
                return
            
            cid = data['cid']
            height = data['height']
            chain_hash = data.get('chain_hash')
            
            current_height = db.get_current_height()
            
            # If we're significantly behind, use snapshot
            if height > current_height + 50:
                logger.info(f"Syncing from snapshot CID: {cid} (height: {height})")
                asyncio.create_task(ipfs_manager.reconstruct_from_snapshot(cid, chain_hash))
                
        except Exception as e:
            logger.error(f"Error handling snapshot: {e}")
    
    async def handle_fork(self, block: Block, peer_id: str):
        """Handle potential fork"""
        try:
            current_height = db.get_current_height()
            
            if block.height > current_height:
                # Request full fork chain
                await self.request_sync(peer_id, current_height + 1, block.height)
                return
            
            # Check if this is part of a longer chain
            # This is simplified - production should request headers first
            logger.info(f"Potential fork at height {block.height}")
            
        except Exception as e:
            logger.error(f"Fork handling error: {e}")
    
    async def request_sync(self, peer_id: str, from_height: int, to_height: int):
        """Request block range from peer"""
        # This would use libp2p request-response protocol
        # Simplified for now
        logger.info(f"Requesting sync from {from_height} to {to_height} from peer {peer_id[:8]}")
    
    async def append_block(self, block: Block):
        """Append validated block to chain"""
        try:
            session = db.get_session()
            
            with session.begin():
                db.store_block(block, session)
            
            logger.info(f"✓ Block {block.height} appended to chain")
            
            # Broadcast to network
            self.publish('/qbc/blocks', {
                'height': block.height,
                'prev_hash': block.prev_hash,
                'proof_data': block.proof_data,
                'transactions': [tx.to_dict() for tx in block.transactions],
                'timestamp': block.timestamp,
                'difficulty': block.difficulty
            })
            
            # Create snapshot if needed
            if block.height % Config.SNAPSHOT_INTERVAL == 0:
                cid = await ipfs_manager.create_snapshot()
                self.publish('/qbc/snapshots', {
                    'cid': cid,
                    'height': block.height,
                    'chain_hash': block.calculate_hash()
                })
            
        except Exception as e:
            logger.error(f"Error appending block: {e}")
    
    def start_listener(self):
        """Start P2P event listener thread"""
        def listen():
            while True:
                try:
                    if not self.node:
                        time.sleep(1)
                        continue
                    
                    events = self.node.poll()
                    
                    for event_str in events:
                        event = json.loads(event_str)
                        
                        if 'topic' not in event or 'data' not in event:
                            continue
                        
                        topic = event['topic']
                        data = json.loads(event['data'])
                        peer_id = event.get('peer_id', 'unknown')
                        
                        # Route to handlers
                        if topic == '/qbc/blocks':
                            self.handle_block_message(data, peer_id)
                        elif topic == '/qbc/transactions':
                            self.handle_transaction_message(data, peer_id)
                        elif topic == '/qbc/snapshots':
                            self.handle_snapshot_message(data, peer_id)
                        
                except Exception as e:
                    logger.error(f"P2P listener error: {e}")
                
                time.sleep(0.01)  # Small delay to prevent CPU spinning
        
        thread = threading.Thread(target=listen, daemon=True, name="P2P-Listener")
        thread.start()
        logger.info("P2P listener started")

p2p = P2PNetwork()

# ============================================================================
# IPFS SNAPSHOT MANAGER
# ============================================================================

class IPFSManager:
    """IPFS snapshot management for chain sync"""
    
    def __init__(self):
        try:
            self.client = ipfshttpclient.connect(Config.IPFS_API)
            logger.info(f"Connected to IPFS: {Config.IPFS_API}")
        except Exception as e:
            logger.error(f"IPFS connection failed: {e}")
            self.client = None
    
    async def create_snapshot(self) -> str:
        """Create and upload ledger snapshot to IPFS"""
        if not self.client:
            return ""
        
        try:
            session = db.get_session()
            
            # Export full state
            blocks = session.execute(text("SELECT * FROM blocks ORDER BY height")).fetchall()
            utxos = session.execute(text("SELECT * FROM utxos WHERE spent = false")).fetchall()
            transactions = session.execute(text("SELECT * FROM transactions WHERE status = 'confirmed'")).fetchall()
            
            snapshot = {
                'version': '1.0',
                'timestamp': time.time(),
                'height': db.get_current_height(),
                'blocks': [dict(row) for row in blocks],
                'utxos': [dict(row) for row in utxos],
                'transactions': [dict(row) for row in transactions],
                'chain_hash': db.get_block(db.get_current_height()).calculate_hash() if blocks else None
            }
            
            # Upload to IPFS
            cid = self.client.add_json(snapshot)
            
            # Pin if Pinata configured
            if Config.PINATA_JWT:
                await self.pin_to_pinata(cid)
            
            logger.info(f"Created snapshot: {cid}")
            return cid
            
        except Exception as e:
            logger.error(f"Snapshot creation failed: {e}")
            return ""
    
    async def reconstruct_from_snapshot(self, cid: str, expected_hash: Optional[str] = None):
        """Reconstruct database from IPFS snapshot"""
        if not self.client:
            logger.error("IPFS not available for reconstruction")
            return
        
        try:
            # Fetch snapshot
            snapshot = self.client.get_json(cid)
            
            # Verify chain hash
            if expected_hash and snapshot.get('chain_hash') != expected_hash:
                raise ValueError(f"Snapshot chain hash mismatch")
            
            session = db.get_session()
            
            with session.begin():
                # Clear existing data (DANGEROUS - backup first in production)
                session.execute(text("TRUNCATE TABLE blocks CASCADE"))
                session.execute(text("TRUNCATE TABLE utxos CASCADE"))
                session.execute(text("TRUNCATE TABLE transactions CASCADE"))
                
                # Restore blocks
                for block_data in snapshot['blocks']:
                    session.execute(
                        text("""
                            INSERT INTO blocks (height, prev_hash, proof_json, difficulty, created_at)
                            VALUES (:h, :ph, :pj, :d, to_timestamp(:ts))
                        """),
                        block_data
                    )
                
                # Restore UTXOs
                for utxo_data in snapshot['utxos']:
                    session.execute(
                        text("""
                            INSERT INTO utxos (txid, vout, amount, address, proof, block_height, spent)
                            VALUES (:txid, :vout, :amount, :address, :proof, :block_height, :spent)
                        """),
                        utxo_data
                    )
                
                # Restore transactions
                for tx_data in snapshot['transactions']:
                    session.execute(
                        text("""
                            INSERT INTO transactions (txid, inputs, outputs, fee, signature, public_key, timestamp, status, block_height)
                            VALUES (:txid, :inputs, :outputs, :fee, :signature, :public_key, :timestamp, :status, :block_height)
                        """),
                        tx_data
                    )
                
                session.commit()
            
            logger.info(f"✓ Reconstructed chain from snapshot {cid} (height: {snapshot['height']})")
            
        except Exception as e:
            logger.error(f"Snapshot reconstruction failed: {e}")
            raise
    
    async def pin_to_pinata(self, cid: str):
        """Pin CID to Pinata for persistence"""
        # Implementation depends on Pinata API
        pass

# ============================================================================
# MINING ENGINE
# ============================================================================

class MiningEngine:
    """VQE-based mining with PoSA consensus"""
    
    def __init__(self):
        self.is_mining = False
        self.mining_thread = None
        self.stats = {
            'blocks_found': 0,
            'total_attempts': 0,
            'current_difficulty': Config.INITIAL_DIFFICULTY
        }
    
    def start(self):
        """Start mining thread"""
        if self.is_mining:
            logger.warning("Mining already running")
            return
        
        self.is_mining = True
        self.mining_thread = threading.Thread(target=self._mine_loop, daemon=True, name="Miner")
        self.mining_thread.start()
        logger.info("⛏️  Mining started")
    
    def stop(self):
        """Stop mining"""
        self.is_mining = False
        if self.mining_thread:
            self.mining_thread.join(timeout=5)
        logger.info("Mining stopped")
    
    def _mine_loop(self):
        """Main mining loop"""
        while self.is_mining:
            try:
                self._mine_block()
            except Exception as e:
                logger.error(f"Mining error: {e}")
                time.sleep(Config.MINING_INTERVAL)
    
    def _mine_block(self):
        """Attempt to mine a single block"""
        # Get current chain state
        current_height = db.get_current_height()
        next_height = current_height + 1
        difficulty = consensus.calculate_difficulty(next_height)
        self.stats['current_difficulty'] = difficulty
        
        # Get previous block
        prev_block = db.get_block(current_height) if current_height >= 0 else None
        prev_hash = prev_block.calculate_hash() if prev_block else '0' * 64
        
        # Select transactions from mempool
        pending_txs = db.get_pending_transactions(limit=1000)
        
        # Filter valid transactions and sort by fee rate
        valid_txs = []
        for tx in pending_txs:
            if self._validate_transaction_for_mining(tx):
                valid_txs.append(tx)
        
        # Sort by fee (descending) and take top transactions
        valid_txs.sort(key=lambda t: t.fee, reverse=True)
        selected_txs = valid_txs[:100]  # Max 100 transactions per block
        
        # Calculate total fees
        total_fees = sum(tx.fee for tx in selected_txs)
        
        # Create coinbase transaction
        reward = consensus.calculate_reward(next_height)
        coinbase = Transaction(
            txid='',  # Will be calculated
            inputs=[],  # Coinbase has no inputs
            outputs=[{
                'address': Config.ADDRESS,
                'amount': reward + total_fees
            }],
            fee=Decimal(0),
            signature='',
            public_key=Config.PUBLIC_KEY_HEX,
            timestamp=time.time(),
            status='pending'
        )
        coinbase.txid = coinbase.calculate_txid()
        
        # Add coinbase to transactions
        block_txs = [coinbase] + selected_txs
        
        # Generate quantum challenge
        hamiltonian = quantum_engine.generate_hamiltonian()
        
        # Optimize VQE
        logger.info(f"Mining block {next_height} with difficulty {difficulty:.4f}")
        
        with Status("[cyan]Optimizing VQE...[/]", console=console):
            params, energy = quantum_engine.optimize_vqe(hamiltonian)
        
        self.stats['total_attempts'] += 1
        
        # Check if solution meets difficulty
        if energy >= difficulty:
            logger.debug(f"Energy {energy:.6f} >= difficulty {difficulty:.6f}, retrying in {Config.MINING_INTERVAL}s")
            time.sleep(Config.MINING_INTERVAL)
            return
        
        # Sign proof
        pk_bytes = bytes.fromhex(Config.PRIVATE_KEY_HEX)
        msg = str(params.tolist()).encode()
        signature = crypto.sign(pk_bytes, msg)
        
        # Create proof data
        proof_data = {
            'challenge': hamiltonian,
            'params': params.tolist(),
            'energy': float(energy),
            'signature': signature.hex(),
            'public_key': Config.PUBLIC_KEY_HEX,
            'miner_address': Config.ADDRESS
        }
        
        # Create block
        block = Block(
            height=next_height,
            prev_hash=prev_hash,
            proof_data=proof_data,
            transactions=block_txs,
            timestamp=time.time(),
            difficulty=difficulty
        )
        
        # Validate own block
        valid, reason = consensus.validate_block(block, prev_block)
        if not valid:
            logger.error(f"Self-validation failed: {reason}")
            return
        
        # Append to chain
        try:
            session = db.get_session()
            with session.begin():
                db.store_block(block, session)
            
            self.stats['blocks_found'] += 1
            
            # Display success
            table = Table(title="⛏️  Block Mined!")
            table.add_column("Property", style="cyan")
            table.add_column("Value", style="green")
            table.add_row("Height", str(block.height))
            table.add_row("Energy", f"{energy:.6f}")
            table.add_row("Difficulty", f"{difficulty:.6f}")
            table.add_row("Transactions", str(len(block_txs)))
            table.add_row("Reward", f"{reward + total_fees:.8f} QBC")
            console.print(Panel(table))
            
            # Broadcast block
            if p2p.node:
                p2p.publish('/qbc/blocks', {
                    'height': block.height,
                    'prev_hash': block.prev_hash,
                    'proof_data': proof_data,
                    'transactions': [tx.to_dict() for tx in block_txs],
                    'timestamp': block.timestamp,
                    'difficulty': block.difficulty
                })
            
            # Save Hamiltonian for research
            session.execute(
                text("""
                    INSERT INTO solved_hamiltonians (hamiltonian, params, energy, miner_address)
                    VALUES (:h, :p, :e, :a)
                """),
                {
                    'h': json.dumps(hamiltonian),
                    'p': json.dumps(params.tolist()),
                    'e': energy,
                    'a': Config.ADDRESS
                }
            )
            session.commit()
            
        except Exception as e:
            logger.error(f"Failed to append mined block: {e}")
        
        time.sleep(Config.MINING_INTERVAL)
    
    def _validate_transaction_for_mining(self, tx: Transaction) -> bool:
        """Validate transaction before including in block"""
        try:
            # Verify signature
            if not crypto.verify_transaction(tx):
                return False
            
            # Verify inputs exist and are unspent
            session = db.get_session()
            input_total = Decimal(0)
            
            for inp in tx.inputs:
                utxo = session.execute(
                    text("SELECT amount, spent FROM utxos WHERE txid=:t AND vout=:v FOR UPDATE"),
                    {'t': inp['txid'], 'v': inp['vout']}
                ).fetchone()
                
                if not utxo or utxo[1]:
                    return False
                
                input_total += Decimal(utxo[0])
            
            # Verify outputs
            output_total = sum(Decimal(o['amount']) for o in tx.outputs)
            
            # Verify fee
            if input_total < output_total + tx.fee:
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Transaction validation error: {e}")
            return False

miner = MiningEngine()

# ============================================================================
# RPC API
# ============================================================================

app = FastAPI(title="Qubitcoin Node RPC", version="1.0.0")

# CORS for web wallets
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dependency for rate limiting (simplified)
async def rate_limit():
    # Implement proper rate limiting in production
    pass

@app.get("/")
async def root():
    """Node information"""
    return {
        "node": "Qubitcoin Full Node",
        "version": "1.0.0",
        "network": "mainnet",
        "height": db.get_current_height(),
        "difficulty": miner.stats['current_difficulty'],
        "peers": len(p2p.reputation.scores) if p2p.node else 0
    }

@app.get("/health")
async def health():
    """Health check"""
    return {
        "status": "healthy",
        "mining": miner.is_mining,
        "p2p": p2p.node is not None,
        "ipfs": ipfs_manager.client is not None,
        "database": True  # TODO: actual DB health check
    }

@app.get("/balance/{address}")
async def get_balance(address: str):
    """Get address balance"""
    try:
        balance = db.get_balance(address)
        utxos = db.get_utxos(address)
        
        return {
            "address": address,
            "balance": str(balance),
            "utxo_count": len(utxos)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/utxos/{address}")
async def get_utxos_endpoint(address: str):
    """Get UTXOs for address"""
    try:
        utxos = db.get_utxos(address)
        return {
            "address": address,
            "utxos": [utxo.to_dict() for utxo in utxos]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/transaction/create")
async def create_transaction(request: Request):
    """Create and sign transaction"""
    try:
        data = await request.json()
        
        # Validate inputs
        from_address = data.get('from_address')
        outputs = data.get('outputs')  # [{'address': str, 'amount': str}]
        
        if not from_address or not outputs:
            raise HTTPException(status_code=400, detail="Missing from_address or outputs")
        
        # Get UTXOs
        utxos = db.get_utxos(from_address)
        
        # Calculate total needed
        output_total = sum(Decimal(o['amount']) for o in outputs)
        fee = max(Config.MIN_FEE, output_total * Config.FEE_RATE)
        total_needed = output_total + fee
        
        # Select UTXOs (simple selection)
        selected_utxos = []
        selected_total = Decimal(0)
        
        for utxo in utxos:
            selected_utxos.append(utxo)
            selected_total += utxo.amount
            
            if selected_total >= total_needed:
                break
        
        if selected_total < total_needed:
            raise HTTPException(status_code=400, detail="Insufficient balance")
        
        # Create change output if needed
        change = selected_total - total_needed
        final_outputs = outputs.copy()
        
        if change > Decimal('0.00000001'):  # Dust threshold
            final_outputs.append({
                'address': from_address,
                'amount': change
            })
        
        # Create transaction
        tx = Transaction(
            txid='',
            inputs=[{'txid': u.txid, 'vout': u.vout} for u in selected_utxos],
            outputs=[{'address': o['address'], 'amount': Decimal(o['amount'])} for o in final_outputs],
            fee=fee,
            signature='',
            public_key=Config.PUBLIC_KEY_HEX,
            timestamp=time.time()
        )
        
        # Calculate txid
        tx.txid = tx.calculate_txid()
        
        # Sign transaction
        private_key = bytes.fromhex(Config.PRIVATE_KEY_HEX)
        tx.signature = crypto.sign_transaction(tx, private_key)
        
        return {
            "transaction": tx.to_dict(),
            "txid": tx.txid
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Transaction creation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/transaction/broadcast")
async def broadcast_transaction(request: Request):
    """Broadcast transaction to network"""
    try:
        data = await request.json()
        
        tx = Transaction(**data)
        
        # Validate transaction
        if not crypto.verify_transaction(tx):
            raise HTTPException(status_code=400, detail="Invalid signature")
        
        # Add to mempool
        session = db.get_session()
        
        try:
            session.execute(
                text("""
                    INSERT INTO transactions 
                    (txid, inputs, outputs, fee, signature, public_key, timestamp, status)
                    VALUES (:txid, :inputs, :outputs, :fee, :sig, :pk, :ts, 'pending')
                """),
                {
                    'txid': tx.txid,
                    'inputs': json.dumps(tx.inputs),
                    'outputs': json.dumps([{'address': o['address'], 'amount': str(o['amount'])} for o in tx.outputs]),
                    'fee': str(tx.fee),
                    'sig': tx.signature,
                    'pk': tx.public_key,
                    'ts': tx.timestamp
                }
            )
            session.commit()
            
            # Broadcast to network
            if p2p.node:
                p2p.publish('/qbc/transactions', tx.to_dict())
            
            return {
                "success": True,
                "txid": tx.txid
            }
            
        except IntegrityError:
            raise HTTPException(status_code=409, detail="Transaction already exists")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Broadcast error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/block/{height}")
async def get_block_endpoint(height: int):
    """Get block by height"""
    try:
        block = db.get_block(height)
        
        if not block:
            raise HTTPException(status_code=404, detail="Block not found")
        
        return {
            "height": block.height,
            "hash": block.calculate_hash(),
            "prev_hash": block.prev_hash,
            "timestamp": block.timestamp,
            "difficulty": block.difficulty,
            "transactions": [tx.to_dict() for tx in block.transactions],
            "proof": block.proof_data
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/mining/stats")
async def mining_stats():
    """Get mining statistics"""
    return {
        "is_mining": miner.is_mining,
        "blocks_found": miner.stats['blocks_found'],
        "total_attempts": miner.stats['total_attempts'],
        "current_difficulty": miner.stats['current_difficulty'],
        "success_rate": miner.stats['blocks_found'] / max(1, miner.stats['total_attempts'])
    }

@app.post("/mining/start")
async def start_mining():
    """Start mining"""
    miner.start()
    return {"status": "Mining started"}

@app.post("/mining/stop")
async def stop_mining():
    """Stop mining"""
    miner.stop()
    return {"status": "Mining stopped"}

@app.get("/chain/info")
async def chain_info():
    """Get blockchain information"""
    session = db.get_session()
    
    height = db.get_current_height()
    supply_result = session.execute(text("SELECT total_minted FROM supply"))
    total_supply = Decimal(supply_result.scalar() or 0)
    
    return {
        "height": height,
        "total_supply": str(total_supply),
        "max_supply": str(Config.MAX_SUPPLY),
        "current_reward": str(consensus.calculate_reward(height + 1)),
        "next_halving": Config.HALVING_INTERVAL - (height % Config.HALVING_INTERVAL)
    }

@app.get("/mempool")
async def mempool_info():
    """Get mempool information"""
    pending = db.get_pending_transactions()
    
    total_fees = sum(tx.fee for tx in pending)
    
    return {
        "size": len(pending),
        "total_fees": str(total_fees),
        "transactions": [tx.to_dict() for tx in pending[:20]]  # First 20
    }

# ============================================================================
# STARTUP & SHUTDOWN
# ============================================================================

@app.on_event("startup")
async def startup():
    """Initialize node on startup"""
    logger.info("=" * 60)
    logger.info("Qubitcoin Full Node Starting")
    logger.info("=" * 60)
    
    # Initialize P2P network
    p2p.initialize()
    p2p.start_listener()
    
    # Check if we need to bootstrap from snapshot
    current_height = db.get_current_height()
    if current_height < 0:
        logger.info("Genesis node - no bootstrap needed")
    else:
        logger.info(f"Current chain height: {current_height}")
    
    # Start mining if configured
    if os.getenv('AUTO_MINE', 'true').lower() == 'true':
        miner.start()
    
    logger.info("✓ Node ready")

@app.on_event("shutdown")
async def shutdown():
    """Cleanup on shutdown"""
    logger.info("Shutting down node...")
    
    miner.stop()
    
    logger.info("✓ Node stopped")

# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    
    # Production server configuration
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=Config.RPC_PORT,
        workers=1,  # Single worker for shared state
        log_level="debug" if os.getenv('DEBUG') == 'true' else "info",
        access_log=True
    )
