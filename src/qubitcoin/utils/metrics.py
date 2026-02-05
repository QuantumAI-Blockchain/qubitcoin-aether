"""
Prometheus metrics for monitoring
Exports key performance indicators
"""
from prometheus_client import Counter, Gauge, Histogram, generate_latest, CONTENT_TYPE_LATEST
from prometheus_fastapi_instrumentator import Instrumentator  # Added for FastAPI integration (install if needed: pip install prometheus-fastapi-instrumentator)

# Blockchain metrics
blocks_mined = Counter('qbc_blocks_mined_total', 'Total blocks mined by this node')
blocks_received = Counter('qbc_blocks_received_total', 'Total blocks received from network')
current_height_metric = Gauge('qbc_blockchain_height', 'Current blockchain height')
total_supply_metric = Gauge('qbc_total_supply', 'Total QBC in circulation')

# Mining metrics
mining_attempts = Counter('qbc_mining_attempts_total', 'Total mining attempts')
current_difficulty_metric = Gauge('qbc_difficulty', 'Current mining difficulty')
vqe_optimization_time = Histogram('qbc_vqe_optimization_seconds', 'VQE optimization time')
block_validation_time = Histogram('qbc_block_validation_seconds', 'Block validation time')

# Network metrics
active_peers = Gauge('qbc_active_peers', 'Number of active P2P peers')
messages_sent = Counter('qbc_messages_sent_total', 'Total P2P messages sent', ['topic'])
messages_received = Counter('qbc_messages_received_total', 'Total P2P messages received', ['topic'])

# Transaction metrics
transactions_pending = Gauge('qbc_transactions_pending', 'Transactions in mempool')
transactions_confirmed = Counter('qbc_transactions_confirmed_total', 'Total confirmed transactions')

# Quantum metrics
quantum_backend_metric = Gauge('qbc_quantum_backend', 'Quantum backend type (0=local, 1=simulator, 2=ibm)')
circuit_depth_metric = Gauge('qbc_circuit_depth', 'Current ansatz circuit depth')

def setup_metrics(app):
    """Setup Prometheus metrics for FastAPI app"""
    instrumentator = Instrumentator().instrument(app).expose(app)
    return instrumentator

# Export functions
__all__ = [
    'blocks_mined',
    'blocks_received',
    'current_height_metric',
    'total_supply_metric',
    'mining_attempts',
    'current_difficulty_metric',
    'vqe_optimization_time',
    'block_validation_time',
    'active_peers',
    'messages_sent',
    'messages_received',
    'transactions_pending',
    'transactions_confirmed',
    'quantum_backend_metric',
    'circuit_depth_metric',
    'setup_metrics',  # Added to __all__
    'generate_latest',
    'CONTENT_TYPE_LATEST'
]
