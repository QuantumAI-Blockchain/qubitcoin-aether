"""
Prometheus metrics for monitoring
Exports key performance indicators for QBC, QVM, and AGI
"""
from prometheus_client import Counter, Gauge, Histogram, generate_latest, CONTENT_TYPE_LATEST
from prometheus_fastapi_instrumentator import Instrumentator

# ============================================================================
# BLOCKCHAIN METRICS
# ============================================================================
blocks_mined = Counter('qbc_blocks_mined_total', 'Total blocks mined by this node')
blocks_received = Counter('qbc_blocks_received_total', 'Total blocks received from network')
current_height_metric = Gauge('qbc_blockchain_height', 'Current blockchain height')
total_supply_metric = Gauge('qbc_total_supply', 'Total QBC in circulation')
current_difficulty_metric = Gauge('qbc_difficulty', 'Current mining difficulty')
network_hashrate_metric = Gauge('qbc_network_hashrate', 'Estimated network hashrate')
avg_block_time_metric = Gauge('qbc_avg_block_time_seconds', 'Average block time (last 100 blocks)')
blockchain_size_metric = Gauge('qbc_blockchain_size_bytes', 'Total blockchain size in bytes')

# ============================================================================
# MINING METRICS
# ============================================================================
mining_attempts = Counter('qbc_mining_attempts_total', 'Total mining attempts')
vqe_optimization_time = Histogram('qbc_vqe_optimization_seconds', 'VQE optimization time')
block_validation_time = Histogram('qbc_block_validation_seconds', 'Block validation time')
alignment_score_metric = Gauge('qbc_alignment_score', 'Current SUSY alignment score (0-100)')
best_alignment_ever = Gauge('qbc_best_alignment_ever', 'Best alignment score achieved')

# ============================================================================
# NETWORK METRICS  
# ============================================================================
active_peers = Gauge('qbc_active_peers', 'Number of active P2P peers')
rust_p2p_peers = Gauge('qbc_rust_p2p_peers', 'Number of Rust P2P network peers')
messages_sent = Counter('qbc_messages_sent_total', 'Total P2P messages sent', ['topic'])
messages_received = Counter('qbc_messages_received_total', 'Total P2P messages received', ['topic'])

# ============================================================================
# TRANSACTION METRICS
# ============================================================================
transactions_pending = Gauge('qbc_transactions_pending', 'Transactions in mempool')
transactions_confirmed = Counter('qbc_transactions_confirmed_total', 'Total confirmed transactions')
mempool_size_bytes = Gauge('qbc_mempool_size_bytes', 'Mempool size in bytes')
avg_tx_fee = Gauge('qbc_avg_transaction_fee', 'Average transaction fee')

# ============================================================================
# QUANTUM RESEARCH METRICS
# ============================================================================
quantum_backend_metric = Gauge('qbc_quantum_backend', 'Quantum backend type (0=local, 1=simulator, 2=ibm)')
circuit_depth_metric = Gauge('qbc_circuit_depth', 'Current ansatz circuit depth')
active_hamiltonians = Gauge('qbc_active_hamiltonians', 'Number of active Hamiltonians')
vqe_solutions_total = Counter('qbc_vqe_solutions_total', 'Total VQE solutions found')
research_contributions = Counter('qbc_research_contributions_total', 'Total scientific contributions')

# ============================================================================
# QVM (SMART CONTRACT) METRICS
# ============================================================================
total_contracts = Gauge('qbc_total_contracts', 'Total deployed smart contracts')
active_contracts = Gauge('qbc_active_contracts', 'Currently active smart contracts')
contract_executions_total = Counter('qbc_contract_executions_total', 'Total contract executions')
contract_execution_time = Histogram('qbc_contract_execution_seconds', 'Contract execution time')
gas_used_total = Counter('qbc_gas_used_total', 'Total gas consumed')
avg_gas_price = Gauge('qbc_avg_gas_price', 'Average gas price (last 100 blocks)')
contract_storage_size = Gauge('qbc_contract_storage_bytes', 'Total contract storage size')

# ============================================================================
# AGI (AETHERTREE) METRICS - THE MAIN EVENT! 🧠
# ============================================================================
phi_current = Gauge('qbc_phi_current', 'Current Phi (Φ) consciousness metric')
phi_threshold_distance = Gauge('qbc_phi_threshold_distance', 'Distance to consciousness threshold (3.0 - Φ)')
knowledge_nodes_total = Gauge('qbc_knowledge_nodes_total', 'Total knowledge graph nodes')
knowledge_edges_total = Gauge('qbc_knowledge_edges_total', 'Total knowledge graph edges')
reasoning_operations_total = Counter('qbc_reasoning_operations_total', 'Total reasoning operations', ['type'])
consciousness_events_total = Counter('qbc_consciousness_events_total', 'Total consciousness events', ['severity'])
integration_score = Gauge('qbc_integration_score', 'Current integration score (0-1)')
differentiation_score = Gauge('qbc_differentiation_score', 'Current differentiation score (0-1)')
causal_chain_length = Gauge('qbc_causal_chain_length', 'Average causal chain length')
agi_training_datasets = Gauge('qbc_agi_training_datasets', 'Number of training datasets')
agi_models_deployed = Gauge('qbc_agi_models_deployed', 'Number of deployed AI models')

# ============================================================================
# IPFS METRICS
# ============================================================================
ipfs_pins_total = Gauge('qbc_ipfs_pins_total', 'Total IPFS pinned content')
ipfs_storage_bytes = Gauge('qbc_ipfs_storage_bytes', 'Total IPFS storage used')
blockchain_snapshots_total = Gauge('qbc_blockchain_snapshots_total', 'Total blockchain snapshots')

def setup_metrics(app):
    """Setup Prometheus metrics for FastAPI app"""
    instrumentator = Instrumentator().instrument(app).expose(app)
    return instrumentator

# Export functions
__all__ = [
    # Blockchain
    'blocks_mined',
    'blocks_received', 
    'current_height_metric',
    'total_supply_metric',
    'current_difficulty_metric',
    'network_hashrate_metric',
    'avg_block_time_metric',
    'blockchain_size_metric',
    
    # Mining
    'mining_attempts',
    'vqe_optimization_time',
    'block_validation_time',
    'alignment_score_metric',
    'best_alignment_ever',
    
    # Network
    'active_peers',
    'rust_p2p_peers',
    'messages_sent',
    'messages_received',
    
    # Transactions
    'transactions_pending',
    'transactions_confirmed',
    'mempool_size_bytes',
    'avg_tx_fee',
    
    # Quantum Research
    'quantum_backend_metric',
    'circuit_depth_metric',
    'active_hamiltonians',
    'vqe_solutions_total',
    'research_contributions',
    
    # QVM
    'total_contracts',
    'active_contracts',
    'contract_executions_total',
    'contract_execution_time',
    'gas_used_total',
    'avg_gas_price',
    'contract_storage_size',
    
    # AGI
    'phi_current',
    'phi_threshold_distance',
    'knowledge_nodes_total',
    'knowledge_edges_total',
    'reasoning_operations_total',
    'consciousness_events_total',
    'integration_score',
    'differentiation_score',
    'causal_chain_length',
    'agi_training_datasets',
    'agi_models_deployed',
    
    # IPFS
    'ipfs_pins_total',
    'ipfs_storage_bytes',
    'blockchain_snapshots_total',
    
    # Setup
    'setup_metrics',
    'generate_latest',
    'CONTENT_TYPE_LATEST'
]
