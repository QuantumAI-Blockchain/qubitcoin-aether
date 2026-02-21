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
avg_block_time_metric = Gauge('qbc_avg_block_time_seconds', 'Average block time (last 100 blocks)')

# ============================================================================
# MINING METRICS
# ============================================================================
mining_attempts = Counter('qbc_mining_attempts_total', 'Total mining attempts')
vqe_optimization_time = Histogram('qbc_vqe_optimization_seconds', 'VQE optimization time')
block_validation_time = Histogram('qbc_block_validation_seconds', 'Block validation time')
alignment_score_metric = Gauge('qbc_alignment_score', 'Current SUSY alignment score (0-100)')

# ============================================================================
# NETWORK METRICS
# ============================================================================
active_peers = Gauge('qbc_active_peers', 'Number of active P2P peers')
rust_p2p_peers = Gauge('qbc_rust_p2p_peers', 'Number of Rust P2P network peers')

# ============================================================================
# TRANSACTION METRICS
# ============================================================================
transactions_pending = Gauge('qbc_transactions_pending', 'Transactions in mempool')
transactions_confirmed = Gauge('qbc_transactions_confirmed_total', 'Total confirmed transactions')

# ============================================================================
# QUANTUM RESEARCH METRICS
# ============================================================================
quantum_backend_metric = Gauge('qbc_quantum_backend', 'Quantum backend type (0=local, 1=simulator, 2=ibm)')
active_hamiltonians = Gauge('qbc_active_hamiltonians', 'Number of active Hamiltonians')
vqe_solutions_total = Gauge('qbc_vqe_solutions_total', 'Total VQE solutions found')

# ============================================================================
# QVM (SMART CONTRACT) METRICS
# ============================================================================
total_contracts = Gauge('qbc_total_contracts', 'Total deployed smart contracts')
active_contracts = Gauge('qbc_active_contracts', 'Currently active smart contracts')

# ============================================================================
# AGI (AETHER TREE) METRICS
# ============================================================================
phi_current = Gauge('qbc_phi_current', 'Current Phi (consciousness metric)')
phi_threshold_distance = Gauge('qbc_phi_threshold_distance', 'Distance to consciousness threshold (3.0 - Phi)')
knowledge_nodes_total = Gauge('qbc_knowledge_nodes_total', 'Total knowledge graph nodes')
knowledge_edges_total = Gauge('qbc_knowledge_edges_total', 'Total knowledge graph edges')
reasoning_operations_total = Gauge('qbc_reasoning_operations_total', 'Total reasoning operations')
consciousness_events_total = Gauge('qbc_consciousness_events_total', 'Total consciousness events')
integration_score = Gauge('qbc_integration_score', 'Current integration score (0-1)')
differentiation_score = Gauge('qbc_differentiation_score', 'Current differentiation score (0-1)')

# ============================================================================
# IPFS METRICS
# ============================================================================
blockchain_snapshots_total = Gauge('qbc_blockchain_snapshots_total', 'Total blockchain snapshots')

def setup_metrics(app):
    """Setup Prometheus metrics for FastAPI app"""
    instrumentator = Instrumentator().instrument(app).expose(app)
    return instrumentator

# Export functions
__all__ = [
    # Blockchain
    'blocks_mined', 'blocks_received', 'current_height_metric',
    'total_supply_metric', 'current_difficulty_metric', 'avg_block_time_metric',
    # Mining
    'mining_attempts', 'vqe_optimization_time', 'block_validation_time',
    'alignment_score_metric',
    # Network
    'active_peers', 'rust_p2p_peers',
    # Transactions
    'transactions_pending', 'transactions_confirmed',
    # Quantum Research
    'quantum_backend_metric', 'active_hamiltonians', 'vqe_solutions_total',
    # QVM
    'total_contracts', 'active_contracts',
    # AGI
    'phi_current', 'phi_threshold_distance', 'knowledge_nodes_total',
    'knowledge_edges_total', 'reasoning_operations_total',
    'consciousness_events_total', 'integration_score', 'differentiation_score',
    # IPFS
    'blockchain_snapshots_total',
    # Setup
    'setup_metrics', 'generate_latest', 'CONTENT_TYPE_LATEST',
]
