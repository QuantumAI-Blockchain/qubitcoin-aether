"""
Frontend-Backend Integration Tests — Full Endpoint Coverage
============================================================

Verifies every endpoint the frontend calls returns the correct response shape.
Uses FastAPI TestClient with mocked subsystems — no running node, no database,
no Docker required.

Tests validate:
- HTTP status codes (200 for success, 503 for missing subsystems)
- Response JSON field names match frontend TypeScript interfaces EXACTLY
- Field types match expectations (int, float, str, bool, list, dict)
- JSON-RPC compliance (eth_*, net_*, web3_*)
"""
import os
import time
import uuid
import pytest
from decimal import Decimal
from unittest.mock import MagicMock, AsyncMock, patch, PropertyMock
from contextlib import contextmanager

# Set rate limit high before any import that might trigger app creation
os.environ['RPC_RATE_LIMIT'] = '100000'

# Set admin API key for auth-protected endpoints
_TEST_ADMIN_KEY = 'test-admin-key-for-unit-tests'
os.environ['ADMIN_API_KEY'] = _TEST_ADMIN_KEY

from qubitcoin.config import Config


# ---------------------------------------------------------------------------
# SHAPE CONTRACTS — exact field names the frontend destructures
# ---------------------------------------------------------------------------

CHAIN_INFO_SHAPE = {
    'chain_id': int, 'height': int, 'total_supply': (int, float),
    'max_supply': (int, float), 'percent_emitted': str,
    'current_era': int, 'current_reward': (int, float),
    'difficulty': (int, float), 'target_block_time': (int, float),
    'peers': int, 'mempool_size': int,
}

PHI_DATA_SHAPE = {
    'phi': (int, float), 'threshold': (int, float), 'above_threshold': bool,
    'integration': (int, float), 'differentiation': (int, float),
    'knowledge_nodes': int, 'knowledge_edges': int, 'blocks_processed': int,
}

PHI_HISTORY_ENTRY_SHAPE = {'block': int, 'phi': (int, float)}

MINING_STATS_SHAPE = {
    'is_mining': bool, 'blocks_found': int, 'total_attempts': int,
    'current_difficulty': (int, float), 'success_rate': (int, float),
}

QVM_INFO_SHAPE = {
    'status': str, 'total_opcodes': int, 'quantum_opcodes': int,
    'total_contracts': int, 'active_contracts': int,
    'chain_id': int, 'block_gas_limit': int,
}

SEPHIROT_STATUS_SHAPE = {
    'susy_pairs': list, 'coherence': (int, float), 'total_violations': int,
}

CHAT_SESSION_SHAPE = {
    'session_id': str, 'created_at': (int, float), 'free_messages': int,
}

CHAT_RESPONSE_SHAPE = {
    'response': str, 'reasoning_trace': list, 'phi_at_response': (int, float),
    'knowledge_nodes_referenced': list, 'proof_of_thought_hash': str,
}

FEE_STATS_SHAPE = {
    'total_collected': str, 'total_events': int, 'by_type': dict, 'recent': list,
}
FEE_AUDIT_SHAPE = {'audit': list}
FEE_TOTAL_SHAPE = {'total_qbc': str}

QUSD_RESERVES_SHAPE = {
    'total_minted': str, 'total_backed': str, 'backing_percentage': (int, float),
}


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

def assert_shape(data: dict, shape: dict, prefix: str = '') -> None:
    """Validate response has required fields with correct types."""
    for field, expected_type in shape.items():
        fq = f"{prefix}.{field}" if prefix else field
        assert field in data, f"Missing field: '{fq}' in {list(data.keys())}"
        if expected_type is not None:
            if isinstance(expected_type, tuple):
                assert isinstance(data[field], expected_type), \
                    f"'{fq}': expected {expected_type}, got {type(data[field]).__name__} = {data[field]!r}"
            else:
                assert isinstance(data[field], expected_type), \
                    f"'{fq}': expected {expected_type.__name__}, got {type(data[field]).__name__} = {data[field]!r}"


def _jsonrpc(client, method: str, params=None, req_id: int = 1) -> dict:
    """Send JSON-RPC call and return parsed response."""
    resp = client.post("/", json={
        "jsonrpc": "2.0", "method": method, "params": params or [], "id": req_id,
    })
    assert resp.status_code == 200, f"JSON-RPC {method} returned {resp.status_code}: {resp.text}"
    data = resp.json()
    assert data.get('jsonrpc') == '2.0', f"Missing jsonrpc field in response"
    assert data.get('id') == req_id, f"ID mismatch: expected {req_id}, got {data.get('id')}"
    return data


# ---------------------------------------------------------------------------
# MOCK FACTORIES
# ---------------------------------------------------------------------------

def _make_mock_session():
    """Create a mock DB session that works as a context manager."""
    session = MagicMock()
    # Default scalar returns
    scalar_mock = MagicMock(return_value=0)
    fetchall_mock = MagicMock(return_value=[])
    fetchone_mock = MagicMock(return_value=None)
    execute_result = MagicMock()
    execute_result.scalar = scalar_mock
    execute_result.fetchall = fetchall_mock
    execute_result.fetchone = fetchone_mock
    session.execute.return_value = execute_result
    return session


def _make_db_manager():
    """Create a mock DatabaseManager."""
    db = MagicMock()
    db.get_current_height.return_value = 100
    db.get_total_supply.return_value = Decimal('1527.00')
    db.get_balance.return_value = Decimal('50.0')
    db.get_utxos.return_value = []
    db.get_pending_transactions.return_value = []
    db.get_block.return_value = None
    db.get_account.return_value = None
    db.get_contract_bytecode.return_value = None
    db.get_storage.return_value = '0' * 64
    db.get_utxo_stats.return_value = {
        'total_utxos': 100, 'total_value': '1527.00', 'spent_utxos': 50,
    }
    db.compute_utxo_commitment.return_value = 'abc123'
    db.get_account_balance.return_value = Decimal('0')
    db.get_block_by_hash.return_value = None
    db.get_receipt.return_value = None
    db.get_sephirot_summary.return_value = {}
    db.get_stakes_by_address.return_value = []
    db.get_node_total_stake.return_value = Decimal('0')
    db.get_total_staked_all_nodes.return_value = Decimal('0')

    # Session context manager
    mock_session = _make_mock_session()

    @contextmanager
    def get_session():
        yield mock_session

    db.get_session = get_session
    db.engine = MagicMock()
    return db


def _make_consensus_engine():
    """Create a mock ConsensusEngine."""
    ce = MagicMock()
    ce.get_emission_stats.return_value = {
        'current_height': 100,
        'total_supply': 1527.0,
        'supply_cap': 3300000000.0,
        'current_reward': 15.27,
        'current_era': 0,
        'percent_emitted': 0.0000463,
        'blocks_until_halving': 15473920,
        'hours_until_halving': 14184.5,
    }
    return ce


def _make_mining_engine():
    """Create a mock MiningEngine."""
    me = MagicMock()
    me.is_mining = False
    me.stats = {
        'blocks_found': 100,
        'total_attempts': 150,
        'current_difficulty': 1.0,
        'best_energy': -0.5,
        'alignment_score': 0.95,
        'uptime': 3600,
        'total_burned': 0.0,
    }
    me.get_stats_snapshot.return_value = dict(me.stats)
    return me


def _make_quantum_engine():
    """Create a mock QuantumEngine."""
    qe = MagicMock()
    qe.estimator = MagicMock()
    qe.backend = MagicMock()
    qe.backend.name = 'statevector_estimator'
    return qe


def _make_ipfs_manager():
    """Create a mock IPFSManager."""
    ipfs = MagicMock()
    ipfs.client = MagicMock()
    return ipfs


def _make_aether_engine():
    """Create a mock AetherEngine."""
    ae = MagicMock()
    ae.phi = MagicMock()
    _phi_result = {
        'phi_value': 0.42,
        'phi_threshold': 3.0,
        'above_threshold': False,
        'integration_score': 0.3,
        'differentiation_score': 0.5,
    }
    ae.phi._last_full_result = _phi_result
    ae.phi.compute_phi.return_value = _phi_result
    ae.phi.get_cached.return_value = _phi_result
    ae.phi.get_history.return_value = [
        {'block_height': 10, 'phi_value': 0.1, 'phi_threshold': 3.0,
         'integration_score': 0.05, 'differentiation_score': 0.08},
        {'block_height': 20, 'phi_value': 0.2, 'phi_threshold': 3.0,
         'integration_score': 0.1, 'differentiation_score': 0.15},
    ]
    ae.kg = MagicMock()
    ae.kg.get_stats.return_value = {
        'total_nodes': 50, 'total_edges': 80, 'blocks_processed': 100,
    }
    ae.kg.nodes = {}
    ae.kg.edges = []
    ae.kg.find_recent.return_value = []
    ae.kg.find_by_type.return_value = []
    ae.kg.find_by_content.return_value = []
    ae.kg.get_domain_stats.return_value = {'domains': {}}
    ae.reasoning = MagicMock()
    ae.reasoning.get_stats.return_value = {
        'total_operations': 50, 'by_type': {'deductive': 20, 'inductive': 20, 'abductive': 10},
    }
    ae.get_stats.return_value = {
        'knowledge_nodes': 50, 'knowledge_edges': 80, 'phi': 0.42,
        'reasoning_operations': 50, 'blocks_processed': 100,
    }
    ae.get_mind_state.return_value = {
        'goals': [], 'contradictions': [], 'knowledge_gaps': [],
        'domain_balance': {}, 'phi': 0.42,
    }
    ae.get_circadian_status.return_value = {
        'phase': 'waking', 'metabolic_rate': 1.0,
    }
    ae.sephirot = {}
    ae._sephirot = {}
    ae._blocks_processed = 0
    return ae


def _make_state_manager():
    """Create a mock StateManager."""
    sm = MagicMock()
    sm.qvm = MagicMock()
    return sm


def _make_fee_collector():
    """Create a mock FeeCollector."""
    fc = MagicMock()
    fc.get_stats.return_value = {
        'total_collected': '0.05',
        'total_events': 5,
        'by_type': {
            'aether_chat': '0.03',
            'aether_query': '0.01',
            'contract_deploy': '0.01',
            'contract_execute': '0',
        },
        'recent': [],
    }
    fc.get_audit_log.return_value = [
        {'fee_type': 'aether_chat', 'amount': '0.01', 'timestamp': time.time()},
    ]
    fc.get_total_fees_collected.return_value = Decimal('0.05')
    fc.collect_fee.return_value = (True, "fee collected", {})
    return fc


def _make_pot_protocol():
    """Create a mock ProofOfThoughtProtocol."""
    pot = MagicMock()
    pot.get_stats.return_value = {
        'task_market': {'open_tasks': 0, 'total_tasks': 0},
        'validators': {'total': 0, 'active': 0},
    }
    pot.task_market = MagicMock()
    pot.task_market.get_open_tasks.return_value = []
    pot.validator_registry = MagicMock()
    pot.validator_registry.get_stats.return_value = {'validators': {}}
    return pot


def _make_bridge_manager():
    """Create a mock BridgeManager."""
    bm = MagicMock()
    bm.get_all_stats = AsyncMock(return_value={
        'chains': ['ethereum', 'solana'],
        'totals': {'tvl': '0', 'total_deposits': 0},
    })
    bm.get_supported_chains = AsyncMock(return_value=[
        'ethereum', 'solana', 'polygon',
    ])
    return bm


def _make_stablecoin_engine():
    """Create a mock StablecoinEngine."""
    se = MagicMock()
    se.get_system_health.return_value = {
        'total_qusd': '3300000000',
        'reserve_backing': '0',
        'cdp_debt': '0',
        'status': 'active',
    }
    se.check_vault_health.return_value = []
    return se


def _make_plugin_manager():
    """Create a mock PluginManager."""
    pm = MagicMock()
    pm.list_plugins.return_value = [
        {'name': 'PrivacyPlugin', 'status': 'running', 'type': 'privacy'},
        {'name': 'OraclePlugin', 'status': 'running', 'type': 'oracle'},
        {'name': 'GovernancePlugin', 'status': 'running', 'type': 'governance'},
        {'name': 'DeFiPlugin', 'status': 'running', 'type': 'defi'},
    ]
    pm.registry = MagicMock()
    pm.registry.get.return_value = None
    return pm


def _make_compliance_engine():
    """Create a mock ComplianceEngine."""
    ce = MagicMock()
    ce.list_policies.return_value = []
    ce.check_compliance.return_value = 'basic'
    ce.is_address_blocked.return_value = False
    ce.circuit_breaker = MagicMock()
    ce.circuit_breaker.to_dict.return_value = {
        'tripped': False, 'trip_count': 0,
    }
    ce.sanctions = MagicMock()
    ce.sanctions._entries = {}
    return ce


def _make_mock_node():
    """Create a mock QubitcoinNode for app.node."""
    node = MagicMock()
    node.rust_p2p = None
    node.p2p = MagicMock()
    node.p2p.connections = []
    node.p2p.running = True
    node.p2p.port = 4001
    node.p2p.peer_id = 'qbc_test_node'
    node.p2p.max_peers = 50
    node.p2p.get_peer_list.return_value = []
    node.p2p.get_stats.return_value = {
        'connected_peers': 0,
        'max_peers': 50,
        'port': 4001,
        'peer_id': 'qbc_test_node',
        'messages_sent': 0,
        'messages_received': 0,
        'blocks_propagated': 0,
        'txs_propagated': 0,
        'connections_made': 0,
        'connections_dropped': 0,
    }
    return node


# ---------------------------------------------------------------------------
# MOCK CHAT SESSION & FEE MANAGER
# ---------------------------------------------------------------------------

class _MockChatSession:
    def __init__(self):
        self.session_id = str(uuid.uuid4())
        self.created_at = time.time()
        self.messages_sent = 0
        self.fees_paid_atoms = 0
        self.messages = []
        self.user_address = ''

    def to_dict(self):
        return {
            'session_id': self.session_id,
            'created_at': self.created_at,
            'messages': [],
            'messages_sent': 0,
        }


# ---------------------------------------------------------------------------
# FIXTURES
# ---------------------------------------------------------------------------

# List of all inline-instantiated classes that must be patched
_PATCH_TARGETS = [
    'qubitcoin.aether.consciousness.ConsciousnessDashboard',
    'qubitcoin.aether.ws_streaming.AetherWSManager',
    'qubitcoin.aether.circulation.CirculationTracker',
    'qubitcoin.qvm.token_indexer.TokenIndexer',
    'qubitcoin.aether.pot_explorer.ProofOfThoughtExplorer',
    'qubitcoin.qvm.regulatory_reports.RegulatoryReportGenerator',
    'qubitcoin.database.pool_monitor.PoolHealthMonitor',
    'qubitcoin.mining.solution_tracker.SolutionVerificationTracker',
    'qubitcoin.mining.capability_detector.VQECapabilityDetector',
    'qubitcoin.storage.snapshot_scheduler.SnapshotScheduler',
    'qubitcoin.storage.solution_archiver.SolutionArchiver',
    'qubitcoin.network.capability_advertisement.CapabilityAdvertiser',
    'qubitcoin.qvm.compliance.ComplianceEngine',
    'qubitcoin.qvm.compliance_proofs.ComplianceProofStore',
    'qubitcoin.aether.chat.AetherChat',
    'qubitcoin.aether.fee_manager.AetherFeeManager',
    'qubitcoin.contracts.fee_calculator.ContractFeeCalculator',
]


class _SyncASGIClient:
    """Synchronous wrapper around httpx.AsyncClient for ASGI apps.

    httpx 0.28+ requires AsyncClient for ASGITransport. This wrapper
    runs async calls via asyncio.run() so tests stay synchronous.
    """
    def __init__(self, app):
        import httpx as _httpx
        self._transport = _httpx.ASGITransport(app=app)
        self._base_url = "http://testserver"

    def _run(self, coro):
        import asyncio
        return asyncio.run(coro)

    def _make_client(self):
        import httpx as _httpx
        return _httpx.AsyncClient(transport=self._transport, base_url=self._base_url)

    def get(self, url, **kwargs):
        async def _do():
            async with self._make_client() as c:
                return await c.get(url, **kwargs)
        return self._run(_do())

    def post(self, url, **kwargs):
        async def _do():
            async with self._make_client() as c:
                return await c.post(url, **kwargs)
        return self._run(_do())

    def put(self, url, **kwargs):
        async def _do():
            async with self._make_client() as c:
                return await c.put(url, **kwargs)
        return self._run(_do())

    def delete(self, url, **kwargs):
        async def _do():
            async with self._make_client() as c:
                return await c.delete(url, **kwargs)
        return self._run(_do())


@pytest.fixture(scope='module')
def app_and_client():
    """Create the FastAPI app with all mocks and return (app, TestClient)."""

    db = _make_db_manager()
    ce = _make_consensus_engine()
    me = _make_mining_engine()
    qe = _make_quantum_engine()
    ipfs = _make_ipfs_manager()
    ae = _make_aether_engine()
    sm = _make_state_manager()
    fc = _make_fee_collector()
    pot = _make_pot_protocol()
    bm = _make_bridge_manager()
    se = _make_stablecoin_engine()
    pm = _make_plugin_manager()
    comp = _make_compliance_engine()

    # Build patchers for all inline-instantiated classes
    patchers = []
    mocks = {}
    for target in _PATCH_TARGETS:
        p = patch(target)
        patchers.append(p)

    # Start all patchers
    for i, p in enumerate(patchers):
        m = p.start()
        target_name = _PATCH_TARGETS[i].split('.')[-1]
        mocks[target_name] = m

    # Configure key mock return values
    # ConsciousnessDashboard
    dashboard_inst = MagicMock()
    dashboard_inst.get_dashboard_data.return_value = {
        'status': {'is_conscious': False, 'phi': 0.42},
        'phi_history': [],
        'events': [],
        'trend': {'trend': 'rising', 'slope': 0.01},
    }
    dashboard_inst.get_phi_history.return_value = [
        {'block_height': 10, 'phi': 0.1, 'is_conscious': False},
    ]
    dashboard_inst.get_events.return_value = []
    dashboard_inst.event_count = 0
    dashboard_inst.get_trend.return_value = {
        'trend': 'stable', 'slope': 0.0, 'window_size': 20,
        'min_phi': 0.0, 'max_phi': 0.5, 'avg_phi': 0.2,
    }
    mocks['ConsciousnessDashboard'].return_value = dashboard_inst

    # AetherWSManager
    ws_inst = MagicMock()
    ws_inst.get_stats.return_value = {
        'connected_clients': 0, 'max_clients': 1000,
        'total_events_broadcast': 0, 'clients': [],
    }
    ws_inst.VALID_EVENTS = {
        'aether_response', 'phi_update', 'consciousness_event',
        'knowledge_node', 'circulation_update', 'token_transfer',
    }
    ws_inst._clients = {}
    mocks['AetherWSManager'].return_value = ws_inst

    # CirculationTracker
    circ_inst = MagicMock()
    circ_inst.get_stats.return_value = {
        'current': None, 'halving_events': 0, 'snapshots_stored': 0,
        'total_fees_collected': '0',
    }
    circ_inst.get_current.return_value = None
    circ_inst.get_history.return_value = []
    circ_inst.get_halving_events.return_value = []
    circ_inst.get_emission_schedule.return_value = []
    mocks['CirculationTracker'].return_value = circ_inst

    # TokenIndexer
    tok_inst = MagicMock()
    tok_inst.get_all_tokens.return_value = []
    tok_inst.get_stats.return_value = {
        'tracked_tokens': 0, 'total_transfers': 0, 'total_unique_holders': 0,
    }
    tok_inst.get_token_info.return_value = None
    tok_inst.get_token_holders.return_value = []
    tok_inst.get_transfers.return_value = []
    tok_inst.get_token_balance.return_value = Decimal('0')
    tok_inst.get_address_tokens.return_value = []
    mocks['TokenIndexer'].return_value = tok_inst

    # ProofOfThoughtExplorer
    pot_exp_inst = MagicMock()
    pot_exp_inst.get_block_thought.return_value = {
        'block_height': 10, 'thought_hash': 'abc', 'phi_value': 0.1,
        'reasoning_steps': [], 'knowledge_nodes_created': 2,
    }
    pot_exp_inst.get_block_range.return_value = []
    pot_exp_inst.get_phi_progression.return_value = []
    pot_exp_inst.get_consciousness_events.return_value = []
    pot_exp_inst.get_reasoning_summary.return_value = {
        'block_height': 10, 'phi_value': 0.1, 'total_steps': 0,
        'reasoning_types': {}, 'conclusions': [],
        'knowledge_nodes_created': 0, 'consciousness_event': None,
    }
    pot_exp_inst.get_stats.return_value = {
        'blocks_explored': 100, 'phi_history_size': 100,
        'total_reasoning_steps': 0, 'consciousness_events': 0,
        'phi_min': 0.0, 'phi_max': 0.5, 'phi_avg': 0.2,
    }
    mocks['ProofOfThoughtExplorer'].return_value = pot_exp_inst

    # RegulatoryReportGenerator
    report_inst = MagicMock()
    report_inst.get_stats.return_value = {
        'total_reports': 0, 'report_types': {},
        'compliance_engine_available': True, 'proof_store_available': True,
    }
    report_inst.list_reports.return_value = []
    mocks['RegulatoryReportGenerator'].return_value = report_inst

    # PoolHealthMonitor
    pool_inst = MagicMock()
    snap_dict = {
        'timestamp': time.time(), 'pool_size': 10, 'checked_in': 10,
        'checked_out': 0, 'overflow': 0, 'checkedout_pct': 0.0,
        'avg_checkout_ms': 0.0, 'total_checkouts': 0, 'total_errors': 0,
        'total_timeouts': 0, 'status': 'healthy',
    }
    snap_obj = MagicMock()
    snap_obj.to_dict.return_value = snap_dict
    pool_inst.get_snapshot.return_value = snap_obj
    pool_inst.get_stats.return_value = {
        'total_checkouts': 0, 'total_checkins': 0, 'total_errors': 0,
        'total_timeouts': 0, 'total_invalidated': 0,
        'avg_checkout_latency_ms': 0.0, 'max_checkout_latency_ms': 0.0,
        'latency_samples': 0, 'history_size': 0,
    }
    pool_inst.get_history.return_value = []
    mocks['PoolHealthMonitor'].return_value = pool_inst

    # SolutionVerificationTracker
    sol_inst = MagicMock()
    sol_inst.get_stats.return_value = {
        'total_solutions': 0, 'verified_solutions': 0,
        'unverified_solutions': 0, 'total_verifications': 0,
        'total_confirmed': 0, 'avg_confidence': 0.0, 'unique_miners': 0,
    }
    sol_inst.get_solution.return_value = None
    sol_inst.get_by_block.return_value = None
    sol_inst.get_top_verified.return_value = []
    sol_inst.get_unverified.return_value = []
    mocks['SolutionVerificationTracker'].return_value = sol_inst

    # VQECapabilityDetector
    cap_inst = MagicMock()
    cap_obj = MagicMock()
    cap_obj.to_dict.return_value = {
        'backend_type': 'local_estimator', 'backend_name': 'statevector',
        'max_qubits': 20, 'is_simulator': True, 'is_available': True,
        'estimated_vqe_time_s': 0.5, 'features': {}, 'detected_at': time.time(),
    }
    cap_inst.detect.return_value = cap_obj
    cap_inst.detect_from_config.return_value = cap_obj
    cap_inst.get_cached.return_value = cap_obj
    cap_inst.get_p2p_advertisement.return_value = {
        'type': 'capability_advertisement', 'backend_type': 'local_estimator',
        'max_qubits': 20, 'is_simulator': True, 'is_available': True,
        'estimated_vqe_time_s': 0.5, 'features': {},
        'timestamp': time.time(),
    }
    mocks['VQECapabilityDetector'].return_value = cap_inst

    # SnapshotScheduler
    snap_sched_inst = MagicMock()
    snap_sched_inst.get_stats.return_value = {
        'total_snapshots': 0, 'total_failures': 0,
        'last_snapshot_height': -1, 'interval_blocks': 1000,
        'history_size': 0, 'success_rate': 0.0,
    }
    snap_sched_inst.get_history.return_value = []
    snap_sched_inst.get_latest.return_value = None
    mocks['SnapshotScheduler'].return_value = snap_sched_inst

    # SolutionArchiver
    arch_inst = MagicMock()
    arch_inst.get_stats.return_value = {
        'total_archives': 0, 'total_solutions_archived': 0,
        'last_archive_height': -1, 'interval_blocks': 1000,
        'history_size': 0, 'cids_stored': 0,
    }
    arch_inst.get_history.return_value = []
    arch_inst.get_all_cids.return_value = []
    mocks['SolutionArchiver'].return_value = arch_inst

    # CapabilityAdvertiser
    cap_adv_inst = MagicMock()
    cap_adv_inst.get_all_peers.return_value = []
    cap_adv_inst.get_peers_by_power.return_value = []
    cap_adv_inst.get_network_summary.return_value = {
        'total_peers': 0, 'active_peers': 0, 'available_miners': 0,
        'stale_peers': 0, 'hardware_nodes': 0, 'simulator_nodes': 0,
        'backend_distribution': {}, 'total_mining_power': 0.0,
        'max_qubit_capacity': 0, 'avg_vqe_time_s': 0.0,
    }
    cap_adv_inst.get_local_advertisement.return_value = {
        'type': 'capability_advertisement', 'backend_type': 'local_estimator',
    }
    cap_adv_inst.set_local_capability.return_value = None
    mocks['CapabilityAdvertiser'].return_value = cap_adv_inst

    # ComplianceEngine (inline created)
    comp_inst = MagicMock()
    comp_inst.list_policies.return_value = []
    comp_inst.check_compliance.return_value = 'basic'
    comp_inst.is_address_blocked.return_value = False
    comp_inst.circuit_breaker = MagicMock()
    comp_inst.circuit_breaker.to_dict.return_value = {'tripped': False, 'trip_count': 0}
    mocks['ComplianceEngine'].return_value = comp_inst

    # ComplianceProofStore
    proof_inst = MagicMock()
    proof_inst.get_stats.return_value = {
        'total_proofs': 0, 'unique_addresses': 0,
        'proof_types': {}, 'max_capacity': 50000,
    }
    proof_inst.get_proof.return_value = None
    proof_inst.get_address_proofs.return_value = []
    proof_inst.verify_proof_chain.return_value = {
        'address': 'test', 'total_proofs': 0, 'valid_proofs': 0,
        'invalid_proofs': 0, 'chain_intact': True, 'details': [],
    }
    mocks['ComplianceProofStore'].return_value = proof_inst

    # AetherChat
    chat_session = _MockChatSession()
    chat_inst = MagicMock()
    chat_inst.create_session.return_value = chat_session
    chat_inst.get_session.return_value = chat_session
    chat_inst.process_message.return_value = {
        'response': 'I am Aether Tree.',
        'reasoning_trace': [],
        'phi_at_response': 0.42,
        'knowledge_nodes_referenced': [1, 2],
        'proof_of_thought_hash': 'abc123def456',
        'session_id': chat_session.session_id,
        'message_index': 0,
        'fee_charged': '0.01',
    }
    mocks['AetherChat'].return_value = chat_inst

    # AetherFeeManager
    fee_mgr_inst = MagicMock()
    fee_mgr_inst.get_fee_info.return_value = {
        'fee_qbc': '0.01', 'is_free': True, 'free_remaining': 5,
        'is_deep_query': False, 'pricing_mode': 'fixed_qbc',
        'usd_target': 0.005, 'qbc_price': 1.0, 'treasury_address': '',
    }
    mocks['AetherFeeManager'].return_value = fee_mgr_inst

    # ContractFeeCalculator
    fee_calc_inst = MagicMock()
    fee_calc_inst.calculate_deploy_fee.return_value = Decimal('1.5')
    mocks['ContractFeeCalculator'].return_value = fee_calc_inst

    # Ensure Config.ADMIN_API_KEY is set for auth-protected endpoints
    from qubitcoin.config import Config
    Config.ADMIN_API_KEY = _TEST_ADMIN_KEY

    # Now create the app
    from qubitcoin.network.rpc import create_rpc_app
    app = create_rpc_app(
        db_manager=db,
        consensus_engine=ce,
        mining_engine=me,
        quantum_engine=qe,
        ipfs_manager=ipfs,
        contract_engine=MagicMock(),
        state_manager=sm,
        aether_engine=ae,
        pot_protocol=pot,
        fee_collector=fc,
        qusd_oracle=MagicMock(),
        compliance_engine=comp,
        aml_monitor=MagicMock(get_alerts=MagicMock(return_value=[])),
        compliance_proof_store=proof_inst,
        tlac_manager=MagicMock(_transactions={}),
        risk_normalizer=MagicMock(normalize=MagicMock(return_value=MagicMock(
            to_dict=MagicMock(return_value={
                'address': 'test', 'total_score': 0.1, 'aml_score': 0.0,
                'graph_score': 0.0, 'compliance_score': 0.0, 'raw_qrisk': 0.0,
                'risk_level': 'low',
            })
        ))),
        plugin_manager=pm,
        decoherence_manager=MagicMock(get_stats=MagicMock(return_value={'states': []})),
        transaction_batcher=MagicMock(get_stats=MagicMock(return_value={'pending': 0})),
        state_channel_manager=MagicMock(get_stats=MagicMock(return_value={'channels': []})),
        qvm_debugger=MagicMock(),
        qsol_compiler=MagicMock(),
        systemic_risk_model=MagicMock(detect_high_risk_connections=MagicMock(return_value=[])),
        tx_graph=MagicMock(build_subgraph=MagicMock(return_value={})),
        stablecoin_engine=se,
        reserve_fee_router=MagicMock(get_stats=MagicMock(return_value={'inflows': []})),
        reserve_verifier=MagicMock(get_stats=MagicMock(return_value={'milestones': []})),
        bridge_manager=bm,
        sephirot_manager=MagicMock(get_status=MagicMock(return_value={})),
        csf_transport=MagicMock(get_stats=MagicMock(return_value={'queue_size': 0})),
        pineal_orchestrator=MagicMock(
            get_status=MagicMock(return_value={
                'phase': 'waking', 'metabolic_rate': 1.0, 'is_conscious': False,
            }),
            tick=MagicMock(return_value={'phase': 'waking', 'metabolic_rate': 1.0}),
        ),
        safety_manager=MagicMock(
            get_stats=MagicMock(return_value={'vetoes': 0, 'evaluations': 0}),
            evaluate_and_decide=MagicMock(return_value=(True, None)),
        ),
        spv_verifier=MagicMock(),
        ipfs_memory=MagicMock(get_stats=MagicMock(return_value={'cache_size': 0})),
        capability_advertiser=cap_adv_inst,
    )

    # Set app.node for P2P endpoints
    app.node = _make_mock_node()

    # Disable rate limiting for tests by setting very high limits
    if hasattr(app.state, 'rate_limit_store'):
        app.state.rate_limit_store['max_read_per_minute'] = 100_000
        app.state.rate_limit_store['max_write_per_minute'] = 100_000

    client = _SyncASGIClient(app)

    yield app, client, {
        'db': db, 'ce': ce, 'me': me, 'qe': qe, 'ipfs': ipfs,
        'ae': ae, 'sm': sm, 'fc': fc, 'pot': pot, 'bm': bm,
        'se': se, 'pm': pm, 'comp': comp,
        'chat_session': chat_session,
        'mocks': mocks,
    }

    # Stop all patchers
    for p in patchers:
        p.stop()


# ---------------------------------------------------------------------------
# TEST CLASSES
# ---------------------------------------------------------------------------

class TestBlockchainEndpoints:
    """Tests for /, /health, /info, /chain/info, /chain/tip, /block/{h}."""

    def test_root(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/")
        assert resp.status_code == 200
        data = resp.json()
        assert data['node'] == f'Qubitcoin Full Node v{Config.NODE_VERSION}'
        assert data['version'] == Config.NODE_VERSION
        assert 'economics' in data
        assert 'features' in data
        assert 'height' in data

    def test_health(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data['status'] == 'healthy'
        assert 'mining' in data
        assert 'database' in data
        assert 'p2p' in data

    def test_info(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/info")
        assert resp.status_code == 200
        data = resp.json()
        assert 'node' in data
        assert 'blockchain' in data
        assert 'mining' in data
        assert 'quantum' in data
        assert 'qvm' in data
        assert 'aether' in data

    def test_chain_info_shape(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/chain/info")
        assert resp.status_code == 200
        data = resp.json()
        assert_shape(data, CHAIN_INFO_SHAPE)

    def test_chain_info_percent_emitted_is_string(self, app_and_client):
        """Frontend parses percent_emitted as a string with % sign."""
        _, client, _ = app_and_client
        resp = client.get("/chain/info")
        data = resp.json()
        assert '%' in data['percent_emitted']

    def test_chain_tip_no_blocks(self, app_and_client):
        _, client, ctx = app_and_client
        ctx['db'].get_current_height.return_value = -1
        resp = client.get("/chain/tip")
        assert resp.status_code == 404
        ctx['db'].get_current_height.return_value = 100  # restore

    def test_block_not_found(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/block/999999")
        assert resp.status_code == 404

    def test_block_found(self, app_and_client):
        _, client, ctx = app_and_client
        block = MagicMock()
        block.to_dict.return_value = {
            'height': 10, 'hash': 'abc', 'prev_hash': '000',
            'timestamp': 1708000000, 'difficulty': 1.0,
        }
        ctx['db'].get_block.return_value = block
        resp = client.get("/block/10")
        assert resp.status_code == 200
        data = resp.json()
        assert data['height'] == 10
        ctx['db'].get_block.return_value = None  # restore


class TestBalanceAndUTXO:
    """Tests for /balance/{addr}, /utxos/{addr}, /mempool, /utxo/stats."""

    def test_balance(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/balance/test_address_abc")
        assert resp.status_code == 200
        data = resp.json()
        assert 'address' in data
        assert 'balance' in data
        assert 'utxo_count' in data
        assert data['address'] == 'test_address_abc'

    def test_utxos(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/utxos/test_address_abc")
        assert resp.status_code == 200
        data = resp.json()
        assert 'address' in data
        assert 'utxos' in data
        assert isinstance(data['utxos'], list)
        assert 'total' in data

    def test_mempool(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/mempool")
        assert resp.status_code == 200
        data = resp.json()
        assert 'size' in data
        assert 'total_fees' in data
        assert 'transactions' in data

    def test_utxo_stats(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/utxo/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert 'utxo_commitment' in data


class TestMiningEndpoints:
    """Tests for /mining/stats, /mining/start, /mining/stop."""

    def test_mining_stats_shape(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/mining/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert_shape(data, MINING_STATS_SHAPE)

    def test_mining_start_no_auth(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.post("/mining/start")
        assert resp.status_code == 403

    def test_mining_start(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.post("/mining/start", headers={'X-Admin-Key': _TEST_ADMIN_KEY})
        assert resp.status_code == 200
        data = resp.json()
        assert 'status' in data

    def test_mining_stop_no_auth(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.post("/mining/stop")
        assert resp.status_code == 403

    def test_mining_stop(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.post("/mining/stop", headers={'X-Admin-Key': _TEST_ADMIN_KEY})
        assert resp.status_code == 200
        data = resp.json()
        assert 'status' in data

    def test_mining_capability(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/mining/capability")
        assert resp.status_code == 200
        data = resp.json()
        assert 'backend_type' in data
        assert 'max_qubits' in data

    def test_mining_capability_advertisement(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/mining/capability/advertisement")
        assert resp.status_code == 200
        data = resp.json()
        assert 'type' in data


class TestEconomicsEndpoints:
    """Tests for /economics/emission, /economics/simulate, /circulation/*."""

    def test_emission(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/economics/emission")
        assert resp.status_code == 200
        data = resp.json()
        assert 'current_height' in data
        assert 'total_supply' in data

    def test_simulate(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/economics/simulate?years=5")
        assert resp.status_code == 200
        data = resp.json()
        assert 'schedule' in data
        assert 'max_supply' in data
        assert 'phi' in data

    def test_circulation_stats(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/circulation/stats")
        assert resp.status_code == 200

    def test_circulation_current_no_data(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/circulation/current")
        assert resp.status_code == 200
        # Returns error message when no data
        data = resp.json()
        assert 'error' in data or 'block_height' in data

    def test_circulation_history(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/circulation/history")
        assert resp.status_code == 200
        data = resp.json()
        assert 'history' in data

    def test_circulation_halvings(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/circulation/halvings")
        assert resp.status_code == 200
        data = resp.json()
        assert 'halvings' in data


class TestQVMEndpoints:
    """Tests for /qvm/info, /qvm/contract/*, /qvm/account/*, /qvm/storage/*."""

    def test_qvm_info_shape(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/qvm/info")
        assert resp.status_code == 200
        data = resp.json()
        assert_shape(data, QVM_INFO_SHAPE)

    def test_qvm_account_not_found(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/qvm/account/0x123abc")
        assert resp.status_code == 200
        data = resp.json()
        assert data['nonce'] == 0
        assert data['is_contract'] is False

    def test_qvm_storage(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/qvm/storage/0x123/0x0")
        assert resp.status_code == 200
        data = resp.json()
        assert 'address' in data
        assert 'key' in data
        assert 'value' in data

    def test_qvm_contract_not_found(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/qvm/contract/0xnonexistent")
        assert resp.status_code == 404

    def test_qvm_deploy_estimate(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/qvm/deploy/estimate?bytecode_size=1024")
        assert resp.status_code == 200
        data = resp.json()
        assert 'fee_qbc' in data
        assert 'pricing_mode' in data

    def test_qvm_decoherence_states(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/qvm/decoherence/states")
        assert resp.status_code == 200

    def test_qvm_batcher_stats(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/qvm/batcher/stats")
        assert resp.status_code == 200

    def test_qvm_state_channels(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/qvm/channels")
        assert resp.status_code == 200


class TestAetherCoreEndpoints:
    """Tests for /aether/info, /aether/phi, /aether/phi/history, etc."""

    def test_aether_info(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/aether/info")
        assert resp.status_code == 200

    def test_aether_phi(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/aether/phi")
        assert resp.status_code == 200
        data = resp.json()
        # compute_phi returns the raw dict
        assert 'phi_value' in data

    def test_aether_phi_history_shape(self, app_and_client):
        """Frontend expects {history: [{block, phi, ...}]} envelope."""
        _, client, _ = app_and_client
        resp = client.get("/aether/phi/history?limit=10")
        assert resp.status_code == 200
        data = resp.json()
        assert 'history' in data
        assert isinstance(data['history'], list)
        if data['history']:
            entry = data['history'][0]
            assert_shape(entry, PHI_HISTORY_ENTRY_SHAPE)

    def test_aether_consciousness_shape(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/aether/consciousness")
        assert resp.status_code == 200
        data = resp.json()
        assert_shape(data, PHI_DATA_SHAPE)

    def test_aether_consciousness_dashboard(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/aether/consciousness/dashboard")
        assert resp.status_code == 200
        data = resp.json()
        assert 'status' in data
        assert 'trend' in data

    def test_aether_consciousness_trend(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/aether/consciousness/trend?window=20")
        assert resp.status_code == 200
        data = resp.json()
        assert 'trend' in data

    def test_aether_consciousness_events(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/aether/consciousness/events?limit=10")
        assert resp.status_code == 200
        data = resp.json()
        assert 'events' in data
        assert 'total' in data

    def test_aether_consciousness_gates(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/aether/consciousness/gates")
        assert resp.status_code == 200
        data = resp.json()
        assert 'block_height' in data
        assert 'gates' in data

    def test_aether_sephirot_shape(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/aether/sephirot")
        assert resp.status_code == 200
        data = resp.json()
        assert_shape(data, SEPHIROT_STATUS_SHAPE)

    def test_aether_mind(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/aether/mind")
        assert resp.status_code == 200
        data = resp.json()
        assert 'phi' in data

    def test_aether_circadian(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/aether/circadian")
        assert resp.status_code == 200
        data = resp.json()
        assert 'phase' in data
        assert 'metabolic_rate' in data

    def test_aether_phi_timeseries(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/aether/phi/timeseries?limit=50")
        assert resp.status_code == 200
        data = resp.json()
        assert 'blocks' in data
        assert 'phi_values' in data
        assert 'threshold' in data


class TestAetherKnowledgeEndpoints:
    """Tests for /aether/knowledge, /aether/knowledge/graph, etc."""

    def test_knowledge_stats(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/aether/knowledge")
        assert resp.status_code == 200
        data = resp.json()
        assert 'total_nodes' in data

    def test_knowledge_graph(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/aether/knowledge/graph?limit=100")
        assert resp.status_code == 200
        data = resp.json()
        assert 'nodes' in data
        assert 'edges' in data
        assert 'total_nodes' in data
        assert 'total_edges' in data

    def test_knowledge_search(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/aether/knowledge/search?type=assertion&limit=10")
        assert resp.status_code == 200
        data = resp.json()
        assert 'nodes' in data
        assert 'count' in data

    def test_knowledge_recent(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/aether/knowledge/recent?count=10")
        assert resp.status_code == 200
        data = resp.json()
        assert 'nodes' in data
        assert 'count' in data

    def test_knowledge_domains(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/aether/knowledge/domains")
        assert resp.status_code == 200

    def test_knowledge_node_not_found(self, app_and_client):
        _, client, ctx = app_and_client
        ctx['ae'].kg.get_node.return_value = None
        resp = client.get("/aether/knowledge/node/999")
        assert resp.status_code == 404


class TestAetherChatEndpoints:
    """Tests for /aether/chat/session, /aether/chat/message, etc."""

    def test_chat_session_shape(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.post("/aether/chat/session",
                           json={'user_address': 'test_addr'})
        assert resp.status_code == 200
        data = resp.json()
        assert_shape(data, CHAT_SESSION_SHAPE)

    def test_chat_message_shape(self, app_and_client):
        _, client, ctx = app_and_client
        resp = client.post("/aether/chat/message", json={
            'message': 'Hello Aether',
            'session_id': ctx['chat_session'].session_id,
            'is_deep_query': False,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert_shape(data, CHAT_RESPONSE_SHAPE)

    def test_chat_fee(self, app_and_client):
        _, client, ctx = app_and_client
        resp = client.get(f"/aether/chat/fee?session_id={ctx['chat_session'].session_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert 'fee_qbc' in data
        assert 'is_free' in data

    def test_chat_history(self, app_and_client):
        _, client, ctx = app_and_client
        resp = client.get(f"/aether/chat/history/{ctx['chat_session'].session_id}")
        assert resp.status_code == 200

    def test_chat_session_not_found(self, app_and_client):
        _, client, ctx = app_and_client
        # Temporarily make get_session return None
        # chat is lazy-created, access through the mock
        orig = ctx['mocks']['AetherChat'].return_value.get_session.return_value
        ctx['mocks']['AetherChat'].return_value.get_session.return_value = None
        resp = client.get("/aether/chat/fee?session_id=nonexistent")
        assert resp.status_code == 404
        ctx['mocks']['AetherChat'].return_value.get_session.return_value = orig


class TestSephirotEndpoints:
    """Tests for /sephirot/nodes, /sephirot/stakes/{addr}, /sephirot/rewards/{addr}."""

    def test_sephirot_nodes(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/sephirot/nodes")
        assert resp.status_code == 200
        data = resp.json()
        assert 'nodes' in data
        assert isinstance(data['nodes'], list)
        assert len(data['nodes']) == 10  # 10 Sephirot

    def test_sephirot_nodes_have_required_fields(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/sephirot/nodes")
        data = resp.json()
        for node in data['nodes']:
            assert 'id' in node
            assert 'name' in node
            assert 'title' in node
            assert 'function' in node
            assert 'min_stake' in node
            assert 'current_stakers' in node
            assert 'total_staked' in node

    def test_sephirot_stakes(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/sephirot/stakes/test_addr")
        assert resp.status_code == 200
        data = resp.json()
        assert 'stakes' in data

    def test_sephirot_rewards(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/sephirot/rewards/test_addr")
        assert resp.status_code == 200
        data = resp.json()
        assert 'total_earned' in data
        assert 'pending_claim' in data
        assert 'claimed' in data


class TestProofOfThoughtEndpoints:
    """Tests for /pot/stats, /aether/pot/{block}, /aether/pot/stats."""

    def test_pot_stats(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/pot/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert 'task_market' in data
        assert 'validators' in data

    def test_pot_tasks(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/pot/tasks")
        assert resp.status_code == 200
        data = resp.json()
        assert 'tasks' in data

    def test_pot_validators(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/pot/validators")
        assert resp.status_code == 200
        data = resp.json()
        assert 'validators' in data

    def test_aether_pot_block(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/aether/pot/10")
        assert resp.status_code == 200
        data = resp.json()
        assert 'block_height' in data

    def test_aether_pot_stats(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/aether/pot/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert 'blocks_explored' in data


class TestFeeEndpoints:
    """Tests for /fees/audit, /fees/total, /fees/stats."""

    def test_fees_audit_shape(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/fees/audit")
        assert resp.status_code == 200
        data = resp.json()
        assert_shape(data, FEE_AUDIT_SHAPE)

    def test_fees_total_shape(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/fees/total")
        assert resp.status_code == 200
        data = resp.json()
        assert_shape(data, FEE_TOTAL_SHAPE)

    def test_fees_stats_shape(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/fees/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert_shape(data, FEE_STATS_SHAPE)


class TestComplianceEndpoints:
    """Tests for /qvm/compliance/proofs/*, /qvm/compliance/reports/*, etc."""

    def test_compliance_proof_stats(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/qvm/compliance/proofs/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert 'total_proofs' in data

    def test_compliance_proof_not_found(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/qvm/compliance/proofs/nonexistent")
        assert resp.status_code == 404

    def test_compliance_address_proofs(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/qvm/compliance/proofs/address/test_addr")
        assert resp.status_code == 200
        data = resp.json()
        assert 'proofs' in data

    def test_compliance_verify_chain(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/qvm/compliance/proofs/verify/test_addr")
        assert resp.status_code == 200
        data = resp.json()
        assert 'chain_intact' in data

    def test_compliance_policies(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/qvm/compliance/policies")
        assert resp.status_code == 200
        data = resp.json()
        assert 'policies' in data

    def test_compliance_check(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/qvm/compliance/check/test_addr")
        assert resp.status_code == 200
        data = resp.json()
        assert 'address' in data
        assert 'kyc_level' in data
        assert 'is_blocked' in data

    def test_circuit_breaker(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/qvm/compliance/circuit-breaker")
        assert resp.status_code == 200
        data = resp.json()
        assert 'tripped' in data

    def test_compliance_reports_stats(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/qvm/compliance/reports/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert 'total_reports' in data

    def test_compliance_reports_list(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/qvm/compliance/reports")
        assert resp.status_code == 200
        data = resp.json()
        assert 'reports' in data

    def test_compliance_aml_alerts(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/qvm/compliance/aml/alerts")
        assert resp.status_code == 200
        data = resp.json()
        assert 'alerts' in data

    def test_compliance_risk(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/qvm/compliance/risk/test_addr")
        assert resp.status_code == 200
        data = resp.json()
        assert 'total_score' in data
        assert 'risk_level' in data

    def test_compliance_tlac(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/qvm/compliance/tlac/transactions")
        assert resp.status_code == 200
        data = resp.json()
        assert 'transactions' in data

    def test_compliance_tx_graph(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/qvm/compliance/graph/test_addr")
        assert resp.status_code == 200
        data = resp.json()
        assert 'graph' in data

    def test_compliance_systemic_risk(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/qvm/compliance/systemic-risk/test_addr")
        assert resp.status_code == 200
        data = resp.json()
        assert 'high_risk_connections' in data


class TestBridgeEndpoints:
    """Tests for /bridge/stats, /bridge/chains."""

    def test_bridge_stats(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/bridge/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert 'chains' in data

    def test_bridge_chains(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/bridge/chains")
        assert resp.status_code == 200
        data = resp.json()
        assert 'chains' in data
        assert isinstance(data['chains'], list)


class TestStablecoinEndpoints:
    """Tests for /qusd/reserves, /qusd/price, /qusd/health."""

    def test_qusd_reserves_shape(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/qusd/reserves")
        assert resp.status_code == 200
        data = resp.json()
        assert_shape(data, QUSD_RESERVES_SHAPE)

    def test_qusd_price(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/qusd/price")
        assert resp.status_code == 200

    def test_qusd_health(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/qusd/health")
        assert resp.status_code == 200

    def test_qusd_debt(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/qusd/debt")
        assert resp.status_code == 200

    def test_qusd_cross_chain(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/qusd/cross-chain")
        assert resp.status_code == 200
        data = resp.json()
        assert 'wrapped_token' in data
        assert 'supported_chains' in data

    def test_qusd_reserves_inflows(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/qusd/reserves/inflows")
        assert resp.status_code == 200

    def test_qusd_reserves_milestones(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/qusd/reserves/milestones")
        assert resp.status_code == 200


class TestPrivacyEndpoints:
    """Tests for /privacy/commitment/*, /privacy/range-proof/*, /privacy/stealth/*."""

    def test_privacy_commitment_create(self, app_and_client):
        _, client, _ = app_and_client
        with patch('qubitcoin.privacy.commitments.PedersenCommitment') as mock_pc:
            result = MagicMock()
            result.to_hex.return_value = '01' * 33
            result.blinding = 42
            mock_pc.commit.return_value = result
            resp = client.post("/privacy/commitment/create",
                               json={'value': 100})
            assert resp.status_code == 200
            data = resp.json()
            assert 'commitment' in data
            assert 'blinding' in data

    def test_privacy_commitment_verify(self, app_and_client):
        _, client, _ = app_and_client
        with patch('qubitcoin.privacy.commitments.PedersenCommitment') as mock_pc:
            recomputed = MagicMock()
            recomputed.to_hex.return_value = '01' * 32
            mock_pc.commit.return_value = recomputed
            resp = client.post("/privacy/commitment/verify", json={
                'commitment': '01' * 32,
                'value': 100,
                'blinding': '0x2a',
            })
            assert resp.status_code == 200
            data = resp.json()
            assert 'valid' in data

    def test_privacy_range_proof_generate(self, app_and_client):
        _, client, _ = app_and_client
        with patch('qubitcoin.privacy.commitments.PedersenCommitment') as mock_pc, \
             patch('qubitcoin.privacy.range_proofs.RangeProofGenerator') as mock_rp:
            commitment = MagicMock()
            commitment.blinding = 42
            commitment.to_hex.return_value = 'aa' * 33
            mock_pc.commit.return_value = commitment
            inst = MagicMock()
            proof = MagicMock()
            proof.to_hex.return_value = 'bb' * 64
            inst.generate.return_value = proof
            mock_rp.return_value = inst
            resp = client.post("/privacy/range-proof/generate",
                               json={'value': 100})
            assert resp.status_code == 200

    def test_privacy_stealth_keygen(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.post("/privacy/stealth/generate-keypair")
        assert resp.status_code == 200
        data = resp.json()
        assert 'spend_pubkey' in data
        assert 'view_pubkey' in data
        assert 'spend_privkey' in data
        assert 'view_privkey' in data
        assert 'public_address' in data


class TestPluginEndpoints:
    """Tests for /qvm/plugins, /qvm/plugins/{name}."""

    def test_list_plugins(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/qvm/plugins")
        assert resp.status_code == 200
        data = resp.json()
        assert 'plugins' in data
        assert isinstance(data['plugins'], list)
        assert len(data['plugins']) == 4

    def test_get_plugin_by_name(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/qvm/plugins/PrivacyPlugin")
        assert resp.status_code == 200
        data = resp.json()
        assert data['name'] == 'PrivacyPlugin'

    def test_get_plugin_not_found(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/qvm/plugins/NonexistentPlugin")
        assert resp.status_code == 404

    def test_defi_plugin_stats(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/qvm/plugins/defi/stats")
        assert resp.status_code == 200

    def test_governance_proposals(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/qvm/plugins/governance/proposals")
        assert resp.status_code == 200
        data = resp.json()
        assert 'proposals' in data


class TestCognitiveEndpoints:
    """Tests for /aether/cognitive/*."""

    def test_cognitive_sephirot_nodes(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/aether/cognitive/sephirot/nodes")
        assert resp.status_code == 200

    def test_cognitive_csf_stats(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/aether/cognitive/csf/stats")
        assert resp.status_code == 200

    def test_cognitive_pineal_status(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/aether/cognitive/pineal/status")
        assert resp.status_code == 200
        data = resp.json()
        assert 'phase' in data
        assert 'metabolic_rate' in data

    def test_cognitive_safety_stats(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/aether/cognitive/safety/stats")
        assert resp.status_code == 200


class TestTokenEndpoints:
    """Tests for /tokens, /tokens/stats, /tokens/{addr}."""

    def test_list_tokens(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/tokens")
        assert resp.status_code == 200
        data = resp.json()
        assert 'tokens' in data

    def test_token_stats(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/tokens/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert 'tracked_tokens' in data

    def test_token_not_found(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/tokens/0xnonexistent")
        assert resp.status_code == 404

    def test_qvm_tokens_for_address(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/qvm/tokens/test_addr")
        assert resp.status_code == 200
        data = resp.json()
        assert 'tokens' in data


class TestSUSYDatabaseEndpoints:
    """Tests for /susy-database."""

    def test_susy_database(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/susy-database")
        assert resp.status_code == 200
        data = resp.json()
        assert 'solutions' in data
        assert 'count' in data
        assert 'description' in data

    def test_susy_database_export_json(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/susy-database/export?format=json&limit=10")
        assert resp.status_code == 200
        data = resp.json()
        assert 'solutions' in data
        assert 'metadata' in data

    def test_susy_verifications_stats(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/susy-database/verifications/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert 'total_solutions' in data

    def test_susy_archives_stats(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/susy-database/archives/stats")
        assert resp.status_code == 200

    def test_susy_archives_cids(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/susy-database/archives/cids")
        assert resp.status_code == 200
        data = resp.json()
        assert 'cids' in data


class TestP2PEndpoints:
    """Tests for /p2p/peers, /p2p/stats."""

    def test_p2p_peers(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/p2p/peers")
        assert resp.status_code == 200
        data = resp.json()
        assert 'type' in data
        assert 'peer_count' in data

    def test_p2p_stats(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/p2p/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert 'network' in data
        assert 'connections' in data

    def test_p2p_capabilities(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/p2p/capabilities")
        assert resp.status_code == 200
        data = resp.json()
        assert 'peers' in data

    def test_p2p_capabilities_summary(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/p2p/capabilities/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert 'total_peers' in data

    def test_p2p_capabilities_local(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/p2p/capabilities/local")
        assert resp.status_code == 200


class TestDatabasePoolEndpoints:
    """Tests for /db/pool/health, /db/pool/stats, /db/pool/history."""

    def test_pool_health(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/db/pool/health")
        assert resp.status_code == 200
        data = resp.json()
        assert 'status' in data

    def test_pool_stats(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/db/pool/stats")
        assert resp.status_code == 200

    def test_pool_history(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/db/pool/history")
        assert resp.status_code == 200
        data = resp.json()
        assert 'history' in data


class TestSnapshotEndpoints:
    """Tests for /snapshots/stats, /snapshots/history, /snapshots/latest."""

    def test_snapshot_stats(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/snapshots/stats")
        assert resp.status_code == 200

    def test_snapshot_history(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/snapshots/history")
        assert resp.status_code == 200
        data = resp.json()
        assert 'history' in data

    def test_snapshot_latest_no_data(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/snapshots/latest")
        assert resp.status_code == 200
        data = resp.json()
        assert 'error' in data  # No snapshots yet


class TestOracleEndpoints:
    """Tests for /oracle/qbc-usd, /oracle/status."""

    def test_oracle_qbc_usd(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/oracle/qbc-usd")
        assert resp.status_code == 200

    def test_oracle_status(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/oracle/status")
        assert resp.status_code == 200


class TestIPFSMemoryEndpoints:
    """Tests for /aether/memory/stats."""

    def test_memory_stats(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/aether/memory/stats")
        assert resp.status_code == 200


class TestLightNodeEndpoints:
    """Tests for /light/headers."""

    def test_light_headers(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/light/headers/0/10")
        assert resp.status_code == 200
        data = resp.json()
        assert 'headers' in data
        assert 'count' in data


class TestWSStatsEndpoints:
    """Tests for /ws/aether/stats."""

    def test_ws_aether_stats(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/ws/aether/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert 'connected_clients' in data


class TestLLMEndpoints:
    """Tests for /aether/llm/stats."""

    def test_llm_stats(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/aether/llm/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert 'llm_enabled' in data


class TestMetricsEndpoint:
    """Test for /metrics (Prometheus)."""

    def test_metrics(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/metrics")
        assert resp.status_code == 200
        # Prometheus text format
        assert 'text/plain' in resp.headers.get('content-type', '') or \
               'openmetrics' in resp.headers.get('content-type', '')


# ---------------------------------------------------------------------------
# JSON-RPC TESTS
# ---------------------------------------------------------------------------

class TestJSONRPC:
    """Tests for eth_*, net_*, web3_* JSON-RPC methods."""

    def test_eth_chainId(self, app_and_client):
        _, client, _ = app_and_client
        data = _jsonrpc(client, 'eth_chainId')
        assert 'result' in data
        assert data['result'] == hex(3303)

    def test_eth_blockNumber(self, app_and_client):
        _, client, _ = app_and_client
        data = _jsonrpc(client, 'eth_blockNumber')
        assert 'result' in data
        # Should be hex string
        assert data['result'].startswith('0x')

    def test_eth_getBalance(self, app_and_client):
        _, client, _ = app_and_client
        data = _jsonrpc(client, 'eth_getBalance', ['0x' + '0' * 40, 'latest'])
        assert 'result' in data
        assert data['result'].startswith('0x')

    def test_eth_gasPrice(self, app_and_client):
        _, client, _ = app_and_client
        data = _jsonrpc(client, 'eth_gasPrice')
        assert 'result' in data
        assert data['result'].startswith('0x')

    def test_net_version(self, app_and_client):
        _, client, _ = app_and_client
        data = _jsonrpc(client, 'net_version')
        assert 'result' in data
        assert data['result'] == str(3303)

    def test_web3_clientVersion(self, app_and_client):
        _, client, _ = app_and_client
        data = _jsonrpc(client, 'web3_clientVersion')
        assert 'result' in data
        assert 'Qubitcoin' in data['result']

    def test_eth_mining(self, app_and_client):
        _, client, _ = app_and_client
        data = _jsonrpc(client, 'eth_mining')
        assert 'result' in data

    def test_eth_getCode(self, app_and_client):
        _, client, _ = app_and_client
        data = _jsonrpc(client, 'eth_getCode', ['0x' + '0' * 40, 'latest'])
        assert 'result' in data
        assert data['result'].startswith('0x')

    def test_eth_getTransactionCount(self, app_and_client):
        _, client, _ = app_and_client
        data = _jsonrpc(client, 'eth_getTransactionCount', ['0x' + '0' * 40, 'latest'])
        assert 'result' in data
        assert data['result'].startswith('0x')

    def test_unknown_method(self, app_and_client):
        _, client, _ = app_and_client
        data = _jsonrpc(client, 'eth_nonexistentMethod')
        assert 'error' in data
        assert data['error']['code'] == -32601

    def test_jsonrpc_batch_id_preserved(self, app_and_client):
        """ID in response matches request."""
        _, client, _ = app_and_client
        data = _jsonrpc(client, 'eth_chainId', req_id=42)
        assert data['id'] == 42

    def test_jsonrpc_version_field(self, app_and_client):
        _, client, _ = app_and_client
        data = _jsonrpc(client, 'eth_chainId')
        assert data['jsonrpc'] == '2.0'


# ---------------------------------------------------------------------------
# FRONTEND RESPONSE SHAPE CONTRACTS — Critical validation
# ---------------------------------------------------------------------------

class TestFrontendResponseShapes:
    """Verify EXACT field names and types for all frontend TypeScript interfaces.

    These are the most critical tests — any mismatch here means the frontend
    will show '---' or crash.
    """

    def test_chain_info_exact_fields(self, app_and_client):
        """Frontend ChainInfo interface."""
        _, client, _ = app_and_client
        data = client.get("/chain/info").json()
        assert_shape(data, CHAIN_INFO_SHAPE)
        # Additional: percent_emitted must end with %
        assert data['percent_emitted'].endswith('%')

    def test_phi_consciousness_exact_fields(self, app_and_client):
        """Frontend PhiData interface."""
        _, client, _ = app_and_client
        data = client.get("/aether/consciousness").json()
        assert_shape(data, PHI_DATA_SHAPE)

    def test_phi_history_block_not_height(self, app_and_client):
        """Frontend expects 'block' NOT 'height' or 'block_height'."""
        _, client, _ = app_and_client
        data = client.get("/aether/phi/history").json()
        assert 'history' in data
        for entry in data['history']:
            assert 'block' in entry, "Frontend expects 'block', not 'block_height'"
            assert 'phi' in entry, "Frontend expects 'phi', not 'phi_value'"

    def test_mining_stats_exact_fields(self, app_and_client):
        """Frontend MiningStats interface."""
        _, client, _ = app_and_client
        data = client.get("/mining/stats").json()
        assert_shape(data, MINING_STATS_SHAPE)

    def test_qvm_info_exact_fields(self, app_and_client):
        """Frontend QVMInfo interface."""
        _, client, _ = app_and_client
        data = client.get("/qvm/info").json()
        assert_shape(data, QVM_INFO_SHAPE)

    def test_sephirot_has_susy_pairs(self, app_and_client):
        """Frontend SephirotStatus requires susy_pairs, coherence, total_violations."""
        _, client, _ = app_and_client
        data = client.get("/aether/sephirot").json()
        assert_shape(data, SEPHIROT_STATUS_SHAPE)
        # Verify susy_pairs structure
        assert len(data['susy_pairs']) == 3
        for pair in data['susy_pairs']:
            assert 'expansion' in pair
            assert 'constraint' in pair

    def test_chat_session_exact_fields(self, app_and_client):
        """Frontend ChatSession interface."""
        _, client, _ = app_and_client
        data = client.post("/aether/chat/session",
                           json={'user_address': 'test'}).json()
        assert_shape(data, CHAT_SESSION_SHAPE)

    def test_chat_message_exact_fields(self, app_and_client):
        """Frontend ChatResponse interface."""
        _, client, ctx = app_and_client
        data = client.post("/aether/chat/message", json={
            'message': 'test',
            'session_id': ctx['chat_session'].session_id,
        }).json()
        assert_shape(data, CHAT_RESPONSE_SHAPE)

    def test_fee_stats_exact_fields(self, app_and_client):
        """Frontend FeeStats interface."""
        _, client, _ = app_and_client
        data = client.get("/fees/stats").json()
        assert_shape(data, FEE_STATS_SHAPE)

    def test_fee_audit_exact_fields(self, app_and_client):
        """Frontend FeeAudit interface."""
        _, client, _ = app_and_client
        data = client.get("/fees/audit").json()
        assert_shape(data, FEE_AUDIT_SHAPE)

    def test_fee_total_exact_fields(self, app_and_client):
        """Frontend FeeTotal interface."""
        _, client, _ = app_and_client
        data = client.get("/fees/total").json()
        assert_shape(data, FEE_TOTAL_SHAPE)

    def test_qusd_reserves_exact_fields(self, app_and_client):
        """Frontend QUSDReserves interface."""
        _, client, _ = app_and_client
        data = client.get("/qusd/reserves").json()
        assert_shape(data, QUSD_RESERVES_SHAPE)

    def test_balance_returns_string(self, app_and_client):
        """Frontend expects balance as string (Decimal serialization)."""
        _, client, _ = app_and_client
        data = client.get("/balance/test_addr").json()
        assert isinstance(data['balance'], str)

    def test_jsonrpc_chain_id_hex(self, app_and_client):
        """MetaMask expects eth_chainId as hex string."""
        _, client, _ = app_and_client
        data = _jsonrpc(client, 'eth_chainId')
        result = data['result']
        assert isinstance(result, str)
        assert result.startswith('0x')
        # Verify it decodes to 3303
        assert int(result, 16) == 3303

    def test_health_has_all_subsystem_flags(self, app_and_client):
        """Frontend dashboard checks these boolean flags."""
        _, client, _ = app_and_client
        data = client.get("/health").json()
        required_flags = [
            'mining', 'database', 'quantum', 'ipfs', 'contracts',
            'qvm', 'aether_tree', 'p2p', 'bridge', 'stablecoin',
            'compliance', 'plugins', 'cognitive', 'privacy',
            'fee_collector', 'spv_verifier',
        ]
        for flag in required_flags:
            assert flag in data, f"Missing health flag: '{flag}'"
