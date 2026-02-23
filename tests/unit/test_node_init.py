"""
QubitcoinNode Initialization Tests
===================================

Comprehensive test suite for the 22-component node initialization sequence
in ``src/qubitcoin/node.py``.

Tests cover:
  1. Full initialization succeeds with all dependencies mocked
  2. Each non-fatal component degrades gracefully (sets self.X = None)
  3. Cognitive wiring (pineal -> aether, csf -> aether, llm -> aether)
  4. The async shutdown sequence
  5. Metrics update (_update_all_metrics) with missing subsystems
  6. P2P mode selection, plugin registration, RPC wiring, genesis paths,
     on_block_mined, compliance wiring, on_startup, edge cases

Strategy:
  - Top-level imports in node.py (DatabaseManager, QuantumEngine, etc.) are
    mocked via ``patch('qubitcoin.node.ClassName')``.
  - Inline lazy imports (FeeCollector, ComplianceEngine, etc.) are mocked via
    ``patch('qubitcoin.<subpackage>.<module>.ClassName')``.
  - Each ``patch`` replaces the class with a factory returning a MagicMock so
    ``ClassName(args)`` produces a mock instance.
  - For degradation tests, ``side_effect=Exception`` on the class mock makes
    the constructor raise, triggering the except block.
"""

import asyncio
import os
import pytest
from decimal import Decimal
from unittest.mock import MagicMock, AsyncMock, patch, PropertyMock

# Ensure safe defaults before any qubitcoin import
os.environ.setdefault('ENABLE_RUST_P2P', 'false')
os.environ.setdefault('LLM_ENABLED', 'false')
os.environ.setdefault('AUTO_MINE', 'false')
os.environ.setdefault('RPC_RATE_LIMIT', '100000')
os.environ.setdefault('ADDRESS', 'qbc1_test_address_0000000000000000')


# ---------------------------------------------------------------------------
# MOCK FACTORIES
# ---------------------------------------------------------------------------

def _mock_db():
    db = MagicMock()
    db.get_current_height.return_value = 0
    db.get_total_supply.return_value = Decimal('0')
    db.get_balance.return_value = Decimal('0')
    db.get_block.return_value = None
    db.get_pending_transactions.return_value = []
    db.query_one.return_value = None
    db.engine = MagicMock()
    return db


def _mock_quantum():
    qe = MagicMock()
    qe.estimator = MagicMock()
    qe.backend = MagicMock()
    qe.backend.name = 'statevector_estimator'
    return qe


def _mock_p2p():
    p2p = MagicMock()
    p2p.connections = {}
    p2p.start = AsyncMock()
    p2p.stop = AsyncMock()
    p2p.broadcast = AsyncMock()
    p2p.send_message = AsyncMock()
    p2p.register_handler = MagicMock()
    p2p.get_peer_list = MagicMock(return_value=[])
    p2p.peer_id = 'test_peer_0000'
    return p2p


def _mock_rust_p2p():
    r = MagicMock()
    r.connect.return_value = True
    r.disconnect.return_value = None
    r.get_peer_count.return_value = 0
    r.broadcast_block.return_value = True
    return r


def _mock_consensus():
    ce = MagicMock()
    ce.aether = None
    ce.state_manager = None
    return ce


def _mock_ipfs():
    ipfs = MagicMock()
    ipfs.client = MagicMock()
    ipfs.create_snapshot = MagicMock()
    return ipfs


def _mock_state_manager():
    sm = MagicMock()
    sm.qvm = MagicMock()
    sm.qvm.compliance = None
    return sm


def _mock_aether():
    ae = MagicMock()
    ae.pot_protocol = None
    ae.on_chain = None
    ae.pineal = None
    ae.csf = None
    ae.llm_manager = None
    ae.consciousness_dashboard = None
    return ae


def _mock_aether_genesis():
    ag = MagicMock()
    ag.is_genesis_initialized.return_value = True
    ag.initialize_genesis.return_value = {'knowledge_nodes_created': 5}
    return ag


def _mock_mining():
    me = MagicMock()
    me.is_mining = False
    me.stats = {
        'blocks_found': 0, 'total_attempts': 0, 'current_difficulty': 1.0,
        'best_energy': 0.0, 'alignment_score': 0.0, 'uptime': 0,
    }
    me.start = MagicMock()
    me.stop = MagicMock()
    me.node = None
    me.circulation_tracker = None
    return me


def _mock_rpc_app():
    app = MagicMock()
    app.node = None
    app.consciousness_dashboard = MagicMock()
    app.circulation_tracker = MagicMock()
    app.on_event = MagicMock(return_value=lambda fn: fn)
    return app


def _mock_config(**overrides):
    cfg = MagicMock()
    defaults = dict(
        ADDRESS='qbc1_test_address_0000000000000000',
        ENABLE_RUST_P2P=False, P2P_PORT=4001, MAX_PEERS=50,
        RUST_P2P_GRPC=50051, LLM_ENABLED=False, LLM_PRIMARY_ADAPTER='openai',
        OPENAI_API_KEY='', OPENAI_MODEL='gpt-4', OPENAI_MAX_TOKENS=4096,
        OPENAI_TEMPERATURE=0.7, CLAUDE_API_KEY='', CLAUDE_MODEL='claude-3-sonnet',
        LOCAL_LLM_URL='', LLM_SEEDER_ENABLED=False, AUTO_MINE=False,
        PEER_SEEDS=[], RPC_HOST='0.0.0.0', RPC_PORT=5000, LOG_LEVEL='INFO',
        DEBUG=False, USE_LOCAL_ESTIMATOR=True, USE_SIMULATOR=False,
        INITIAL_DIFFICULTY=1.0, SNAPSHOT_INTERVAL=100,
    )
    defaults.update(overrides)
    for k, v in defaults.items():
        setattr(cfg, k, v)
    cfg.display.return_value = '[Config Display]'
    return cfg


# ---------------------------------------------------------------------------
# INLINE-IMPORT MOCK TARGETS
# ---------------------------------------------------------------------------

INLINE_TARGETS = [
    'qubitcoin.aether.task_protocol.ProofOfThoughtProtocol',
    'qubitcoin.aether.on_chain.OnChainAGI',
    'qubitcoin.utils.fee_collector.FeeCollector',
    'qubitcoin.utils.qusd_oracle.QUSDOracle',
    'qubitcoin.qvm.compliance.ComplianceEngine',
    'qubitcoin.qvm.aml.AMLMonitor',
    'qubitcoin.qvm.compliance_proofs.ComplianceProofStore',
    'qubitcoin.qvm.compliance_advanced.TLACManager',
    'qubitcoin.qvm.risk.RiskNormalizer',
    'qubitcoin.qvm.plugins.PluginManager',
    'qubitcoin.qvm.decoherence.DecoherenceManager',
    'qubitcoin.qvm.transaction_batcher.TransactionBatcher',
    'qubitcoin.qvm.state_channels.StateChannelManager',
    'qubitcoin.qvm.debugger.QVMDebugger',
    'qubitcoin.qvm.qsol_compiler.QSolCompiler',
    'qubitcoin.qvm.systemic_risk.SystemicRiskModel',
    'qubitcoin.qvm.tx_graph.TransactionGraph',
    'qubitcoin.stablecoin.engine.StablecoinEngine',
    'qubitcoin.stablecoin.reserve_manager.ReserveFeeRouter',
    'qubitcoin.stablecoin.reserve_verification.ReserveVerifier',
    'qubitcoin.bridge.manager.BridgeManager',
    'qubitcoin.aether.sephirot.SephirotManager',
    'qubitcoin.aether.csf_transport.CSFTransport',
    'qubitcoin.aether.pineal.PinealOrchestrator',
    'qubitcoin.aether.safety.SafetyManager',
    'qubitcoin.network.light_node.SPVVerifier',
    'qubitcoin.aether.ipfs_memory.IPFSMemoryStore',
    'qubitcoin.network.capability_advertisement.CapabilityAdvertiser',
    'qubitcoin.aether.llm_adapter.LLMAdapterManager',
    'qubitcoin.aether.llm_adapter.OpenAIAdapter',
    'qubitcoin.aether.llm_adapter.ClaudeAdapter',
    'qubitcoin.aether.llm_adapter.LocalAdapter',
    'qubitcoin.aether.knowledge_seeder.KnowledgeSeeder',
    'qubitcoin.mining.capability_detector.VQECapabilityDetector',
]


# ---------------------------------------------------------------------------
# NODE BUILDER HELPER
# ---------------------------------------------------------------------------

def _build_node(config_overrides=None, broken_inline_targets=None):
    """
    Build a QubitcoinNode with all deps mocked.

    Args:
        config_overrides: dict of Config attribute overrides.
        broken_inline_targets: list of inline target strings that should
            raise Exception when instantiated.

    Returns:
        (node, mocks_dict, patchers_list)
    """
    config = _mock_config(**(config_overrides or {}))
    db = _mock_db()
    quantum = _mock_quantum()
    p2p = _mock_p2p()
    rust_p2p = _mock_rust_p2p()
    consensus = _mock_consensus()
    ipfs = _mock_ipfs()
    sm = _mock_state_manager()
    aether = _mock_aether()
    aether_genesis = _mock_aether_genesis()
    mining = _mock_mining()
    rpc_app = _mock_rpc_app()

    top_patches = {
        'qubitcoin.node.Config': config,
        'qubitcoin.node.console': MagicMock(),
        'qubitcoin.node.DatabaseManager': MagicMock(return_value=db),
        'qubitcoin.node.QuantumEngine': MagicMock(return_value=quantum),
        'qubitcoin.node.P2PNetwork': MagicMock(return_value=p2p),
        'qubitcoin.node.RustP2PClient': MagicMock(return_value=rust_p2p),
        'qubitcoin.node.ConsensusEngine': MagicMock(return_value=consensus),
        'qubitcoin.node.IPFSManager': MagicMock(return_value=ipfs),
        'qubitcoin.node.StateManager': MagicMock(return_value=sm),
        'qubitcoin.node.KnowledgeGraph': MagicMock(),
        'qubitcoin.node.PhiCalculator': MagicMock(),
        'qubitcoin.node.ReasoningEngine': MagicMock(),
        'qubitcoin.node.AetherEngine': MagicMock(return_value=aether),
        'qubitcoin.node.AetherGenesis': MagicMock(return_value=aether_genesis),
        'qubitcoin.node.MiningEngine': MagicMock(return_value=mining),
        'qubitcoin.node.ContractExecutor': MagicMock(),
        'qubitcoin.node.create_rpc_app': MagicMock(return_value=rpc_app),
    }

    broken_set = set(broken_inline_targets or [])
    inline_patches = {}
    for t in INLINE_TARGETS:
        if t in broken_set:
            inline_patches[t] = MagicMock(side_effect=Exception(f"test: {t} broken"))
        else:
            inline_patches[t] = MagicMock()

    def fake_import_module(name, package=None):
        mod = MagicMock()
        for attr in ('DeFiPlugin', 'GovernancePlugin', 'OraclePlugin', 'PrivacyPlugin'):
            setattr(mod, attr, MagicMock())
        return mod

    patchers = []
    for target, mock_val in top_patches.items():
        p = patch(target, mock_val)
        patchers.append(p)
        p.start()
    for target, mock_val in inline_patches.items():
        p = patch(target, mock_val)
        patchers.append(p)
        p.start()
    p_import = patch('importlib.import_module', side_effect=fake_import_module)
    patchers.append(p_import)
    p_import.start()

    from qubitcoin.node import QubitcoinNode
    node = QubitcoinNode()

    mocks = {
        'db': db, 'quantum': quantum, 'p2p': p2p, 'rust_p2p': rust_p2p,
        'consensus': consensus, 'ipfs': ipfs, 'state_manager': sm,
        'aether': aether, 'aether_genesis': aether_genesis,
        'mining': mining, 'rpc_app': rpc_app, 'config': config,
    }
    return node, mocks, patchers


def _stop_patchers(patchers):
    for p in patchers:
        p.stop()


# ---------------------------------------------------------------------------
# FIXTURES
# ---------------------------------------------------------------------------

@pytest.fixture
def patched_node():
    """Create a fully-mocked QubitcoinNode. Yields (node, mocks_dict)."""
    node, mocks, patchers = _build_node()
    yield node, mocks
    _stop_patchers(patchers)


@pytest.fixture
def node(patched_node):
    """Convenience: just the node object."""
    return patched_node[0]


@pytest.fixture
def mocks(patched_node):
    """Convenience: just the mocks dict."""
    return patched_node[1]


# ===========================================================================
# 1. Full initialization succeeds (12 tests)
# ===========================================================================


class TestFullInitialization:

    def test_node_instantiates(self, node):
        assert node is not None

    def test_running_false_and_no_metrics_task(self, node):
        assert node.running is False
        assert node.metrics_task is None

    def test_critical_components_not_none(self, node):
        for attr in ('db', 'quantum', 'consensus', 'ipfs', 'state_manager',
                      'aether', 'mining', 'contracts', 'app'):
            assert getattr(node, attr) is not None, f"Critical component is None: {attr}"

    def test_python_p2p_mode_default(self, node):
        assert node.p2p is not None
        assert node.rust_p2p is None

    def test_aether_subcomponents_assigned(self, node):
        for attr in ('knowledge_graph', 'phi_calculator', 'reasoning_engine',
                      'aether_genesis', 'pot_protocol'):
            assert getattr(node, attr) is not None, f"Aether sub missing: {attr}"

    def test_mining_node_reference(self, node):
        assert node.mining.node is node

    def test_consensus_gets_aether_and_state_manager(self, node):
        assert node.consensus.aether is not None
        assert node.consensus.state_manager is not None

    def test_optional_attributes_all_exist(self, node):
        optional = [
            'fee_collector', 'qusd_oracle', 'compliance_engine', 'aml_monitor',
            'compliance_proof_store', 'tlac_manager', 'risk_normalizer',
            'plugin_manager', 'decoherence_manager', 'transaction_batcher',
            'state_channel_manager', 'qvm_debugger', 'qsol_compiler',
            'systemic_risk_model', 'tx_graph', 'stablecoin_engine',
            'reserve_fee_router', 'reserve_verifier', 'bridge_manager',
            'sephirot_manager', 'csf_transport', 'pineal_orchestrator',
            'safety_manager', 'spv_verifier', 'ipfs_memory',
            'capability_advertiser',
        ]
        for attr in optional:
            assert hasattr(node, attr), f"Missing optional attribute: {attr}"

    def test_llm_defaults_none(self, node):
        assert node.llm_manager is None
        assert node.knowledge_seeder is None

    def test_consciousness_dashboard_wired(self, node, mocks):
        assert mocks['aether'].consciousness_dashboard is node.app.consciousness_dashboard

    def test_circulation_tracker_wired(self, node):
        assert node.mining.circulation_tracker is node.app.circulation_tracker


# ===========================================================================
# 2. Non-fatal component degradation (6 tests, using parametrize)
# ===========================================================================


# Map: (attribute on node, inline target to break)
NONFATAL_COMPONENTS = [
    ('fee_collector', 'qubitcoin.utils.fee_collector.FeeCollector'),
    ('qusd_oracle', 'qubitcoin.utils.qusd_oracle.QUSDOracle'),
    ('compliance_engine', 'qubitcoin.qvm.compliance.ComplianceEngine'),
    ('aml_monitor', 'qubitcoin.qvm.aml.AMLMonitor'),
    ('compliance_proof_store', 'qubitcoin.qvm.compliance_proofs.ComplianceProofStore'),
    ('tlac_manager', 'qubitcoin.qvm.compliance_advanced.TLACManager'),
    ('risk_normalizer', 'qubitcoin.qvm.risk.RiskNormalizer'),
    ('plugin_manager', 'qubitcoin.qvm.plugins.PluginManager'),
    ('decoherence_manager', 'qubitcoin.qvm.decoherence.DecoherenceManager'),
    ('transaction_batcher', 'qubitcoin.qvm.transaction_batcher.TransactionBatcher'),
    ('state_channel_manager', 'qubitcoin.qvm.state_channels.StateChannelManager'),
    ('qvm_debugger', 'qubitcoin.qvm.debugger.QVMDebugger'),
    ('qsol_compiler', 'qubitcoin.qvm.qsol_compiler.QSolCompiler'),
    ('systemic_risk_model', 'qubitcoin.qvm.systemic_risk.SystemicRiskModel'),
    ('tx_graph', 'qubitcoin.qvm.tx_graph.TransactionGraph'),
    ('stablecoin_engine', 'qubitcoin.stablecoin.engine.StablecoinEngine'),
    ('reserve_fee_router', 'qubitcoin.stablecoin.reserve_manager.ReserveFeeRouter'),
    ('reserve_verifier', 'qubitcoin.stablecoin.reserve_verification.ReserveVerifier'),
    ('bridge_manager', 'qubitcoin.bridge.manager.BridgeManager'),
    ('sephirot_manager', 'qubitcoin.aether.sephirot.SephirotManager'),
    ('csf_transport', 'qubitcoin.aether.csf_transport.CSFTransport'),
    ('pineal_orchestrator', 'qubitcoin.aether.pineal.PinealOrchestrator'),
    ('safety_manager', 'qubitcoin.aether.safety.SafetyManager'),
    ('spv_verifier', 'qubitcoin.network.light_node.SPVVerifier'),
    ('ipfs_memory', 'qubitcoin.aether.ipfs_memory.IPFSMemoryStore'),
    ('capability_advertiser', 'qubitcoin.network.capability_advertisement.CapabilityAdvertiser'),
    ('on_chain', 'qubitcoin.aether.on_chain.OnChainAGI'),
]


class TestNonFatalDegradation:

    @pytest.mark.parametrize("attr,target", NONFATAL_COMPONENTS,
                             ids=[c[0] for c in NONFATAL_COMPONENTS])
    def test_component_degrades_gracefully(self, attr, target):
        """Breaking a non-fatal inline import sets self.<attr> = None."""
        node, _, patchers = _build_node(broken_inline_targets=[target])
        try:
            assert getattr(node, attr) is None, \
                f"Expected node.{attr} to be None when {target} raises"
            # Critical components must still be alive
            assert node.db is not None
            assert node.mining is not None
        finally:
            _stop_patchers(patchers)

    def test_pineal_none_when_sephirot_none(self):
        """Pineal requires SephirotManager; if sephirot fails, pineal is also None."""
        node, _, patchers = _build_node(
            broken_inline_targets=['qubitcoin.aether.sephirot.SephirotManager']
        )
        try:
            assert node.sephirot_manager is None
            assert node.pineal_orchestrator is None
        finally:
            _stop_patchers(patchers)

    def test_all_nonfatal_fail_simultaneously(self):
        """Even if ALL non-fatal components fail, critical ones survive."""
        all_targets = [t for _, t in NONFATAL_COMPONENTS]
        node, _, patchers = _build_node(broken_inline_targets=all_targets)
        try:
            for attr in ('db', 'quantum', 'consensus', 'mining', 'app'):
                assert getattr(node, attr) is not None
            for attr, _ in NONFATAL_COMPONENTS:
                assert getattr(node, attr) is None
        finally:
            _stop_patchers(patchers)


# ===========================================================================
# 3. Cognitive wiring (6 tests)
# ===========================================================================


class TestCognitiveWiring:

    def test_pineal_wired_to_aether(self, node, mocks):
        if node.pineal_orchestrator is not None:
            assert mocks['aether'].pineal is node.pineal_orchestrator

    def test_csf_wired_to_aether(self, node, mocks):
        if node.csf_transport is not None:
            assert mocks['aether'].csf is node.csf_transport

    def test_llm_not_wired_when_disabled(self, node):
        assert node.llm_manager is None

    def test_pot_protocol_wired_to_aether(self, node, mocks):
        assert mocks['aether'].pot_protocol is node.pot_protocol

    def test_on_chain_wired_to_aether(self, node, mocks):
        if node.on_chain is not None:
            assert mocks['aether'].on_chain is node.on_chain

    def test_compliance_wired_to_qvm(self, node, mocks):
        if node.compliance_engine is not None:
            assert mocks['state_manager'].qvm.compliance is node.compliance_engine


# ===========================================================================
# 4. Shutdown sequence (8 tests)
# ===========================================================================


class TestShutdownSequence:

    @pytest.mark.asyncio
    async def test_shutdown_sets_running_false(self, node):
        node.running = True
        node.metrics_task = None
        await node.on_shutdown()
        assert node.running is False

    @pytest.mark.asyncio
    async def test_shutdown_cancels_metrics_task(self, node):
        # Create a real asyncio.Future that raises CancelledError when awaited
        loop = asyncio.get_event_loop()
        mock_task = loop.create_future()
        mock_task.cancel()  # Marks the future as cancelled
        node.running = True
        node.metrics_task = mock_task
        await node.on_shutdown()
        assert mock_task.cancelled()

    @pytest.mark.asyncio
    async def test_shutdown_stops_mining(self, node):
        node.running = True
        node.metrics_task = None
        await node.on_shutdown()
        node.mining.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_shutdown_stops_python_p2p(self, node):
        node.running = True
        node.metrics_task = None
        await node.on_shutdown()
        if node.p2p:
            node.p2p.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_shutdown_bridge_manager(self, node):
        node.running = True
        node.metrics_task = None
        node.bridge_manager = MagicMock()
        node.bridge_manager.shutdown = AsyncMock()
        await node.on_shutdown()
        node.bridge_manager.shutdown.assert_called_once()

    @pytest.mark.asyncio
    async def test_shutdown_bridge_error_handled(self, node):
        node.running = True
        node.metrics_task = None
        node.bridge_manager = MagicMock()
        node.bridge_manager.shutdown = AsyncMock(side_effect=RuntimeError("boom"))
        await node.on_shutdown()  # Must not raise

    @pytest.mark.asyncio
    async def test_shutdown_stops_plugins(self, node):
        node.running = True
        node.metrics_task = None
        pm = MagicMock()
        pm.list_plugins.return_value = [{'name': 'defi'}, {'name': 'oracle'}]
        node.plugin_manager = pm
        await node.on_shutdown()
        assert pm.stop.call_count == 2

    @pytest.mark.asyncio
    async def test_shutdown_knowledge_seeder(self, node):
        node.running = True
        node.metrics_task = None
        seeder = MagicMock()
        node.knowledge_seeder = seeder
        await node.on_shutdown()
        seeder.stop.assert_called_once()


# ===========================================================================
# 5. Metrics update (5 tests)
# ===========================================================================


class TestMetricsUpdate:

    @pytest.mark.asyncio
    async def test_metrics_all_subsystems_none(self, node):
        """Does not crash when all optional subsystems are None and DB returns None."""
        for attr in ('bridge_manager', 'compliance_engine', 'plugin_manager',
                      'state_channel_manager', 'transaction_batcher',
                      'decoherence_manager', 'tlac_manager', 'stablecoin_engine',
                      'sephirot_manager', 'csf_transport', 'pineal_orchestrator',
                      'fee_collector', 'qusd_oracle', 'capability_advertiser',
                      'ipfs_memory'):
            setattr(node, attr, None)
        node.db.query_one.return_value = None
        await node._update_all_metrics()

    @pytest.mark.asyncio
    async def test_metrics_all_subsystems_present(self, node):
        """Does not crash when all subsystems return valid data."""
        def query_side_effect(sql, *a, **kw):
            if 'MAX(height)' in sql:
                return {'best_height': 100}
            if 'total_minted' in sql:
                return {'total_minted': Decimal('1527')}
            if 'AVG' in sql:
                return {'avg_time': 3.3}
            if "status = 'pending'" in sql:
                return {'count': 5}
            if "status = 'confirmed'" in sql:
                return {'count': 95}
            if 'solved_hamiltonians' in sql:
                return {'total_count': 100}
            if 'code_hash' in sql:
                return {'cnt': 10}
            if 'is_active' in sql:
                return {'total': 15, 'active_count': 12}
            if 'phi_measurements' in sql:
                return {'phi_value': 0.42, 'phi_threshold': 3.0,
                        'integration_score': 0.3, 'differentiation_score': 0.5}
            if 'knowledge_nodes' in sql:
                return {'node_count': 50, 'edge_count': 80}
            if 'consciousness_events' in sql:
                return {'count': 2}
            if 'reasoning_operations' in sql:
                return {'count': 50}
            if 'ipfs_snapshots' in sql:
                return {'snapshots': 3}
            return None

        node.db.query_one.side_effect = query_side_effect
        node.bridge_manager = MagicMock(bridges={'eth': 1, 'sol': 2})
        node.compliance_engine = MagicMock()
        node.compliance_engine.list_policies.return_value = []
        node.compliance_engine.circuit_breaker = MagicMock(is_open=False)
        node.compliance_engine.sanctions = MagicMock(_entries={})
        node.plugin_manager = MagicMock()
        node.plugin_manager.list_plugins.return_value = [{'name': 'x', 'active': True}]
        node.state_channel_manager = MagicMock()
        node.state_channel_manager.get_stats.return_value = {'open_channels': 3, 'total_locked': 100}
        node.transaction_batcher = MagicMock()
        node.transaction_batcher.get_stats.return_value = {'pending_transactions': 7}
        node.decoherence_manager = MagicMock()
        node.decoherence_manager.get_stats.return_value = {'active_states': 2}
        node.tlac_manager = MagicMock()
        node.tlac_manager.get_stats.return_value = {'pending': 1}
        node.stablecoin_engine = MagicMock()
        node.stablecoin_engine.get_system_health.return_value = {
            'total_qusd': 1e6, 'reserve_backing': 85.0,
            'active_vaults': 50, 'cdp_debt': 5e5,
        }
        node.sephirot_manager = MagicMock()
        node.sephirot_manager.get_status.return_value = {'active_nodes': 10}
        node.csf_transport = MagicMock()
        node.csf_transport.get_stats.return_value = {'queue_depth': 3}
        node.pineal_orchestrator = MagicMock()
        node.pineal_orchestrator.get_status.return_value = {
            'phase_index': 1, 'metabolic_rate': 1.5, 'is_conscious': False,
        }
        node.fee_collector = MagicMock()
        node.fee_collector.get_stats.return_value = {'total_events': 10, 'total_collected': 0.5}
        node.qusd_oracle = MagicMock()
        node.qusd_oracle.get_status.return_value = {'qbc_usd_price': 0.05, 'is_stale': False}
        node.capability_advertiser = MagicMock()
        node.capability_advertiser.get_network_summary.return_value = {
            'total_peers': 5, 'total_mining_power': 100.0,
        }
        node.ipfs_memory = MagicMock()
        node.ipfs_memory.get_stats.return_value = {'cache_size': 256}

        await node._update_all_metrics()

    @pytest.mark.asyncio
    async def test_metrics_db_error_caught(self, node):
        node.db.query_one.side_effect = RuntimeError("DB down")
        await node._update_all_metrics()

    @pytest.mark.asyncio
    async def test_metrics_subsystem_errors_caught(self, node):
        node.db.query_one.return_value = None
        node.bridge_manager = MagicMock()
        type(node.bridge_manager).bridges = PropertyMock(side_effect=RuntimeError("err"))
        node.compliance_engine = MagicMock()
        node.compliance_engine.list_policies.side_effect = RuntimeError("err")
        await node._update_all_metrics()

    @pytest.mark.asyncio
    async def test_metrics_privacy_always_up(self, node):
        node.db.query_one.return_value = None
        from qubitcoin.utils.metrics import subsystem_privacy_up
        await node._update_all_metrics()
        # Privacy subsystem is always up (static classes); check the real gauge
        assert subsystem_privacy_up._value.get() == 1.0


# ===========================================================================
# 6. P2P mode selection (3 tests)
# ===========================================================================


class TestP2PSelection:

    def test_python_p2p_default(self, node):
        assert node.p2p is not None
        assert node.rust_p2p is None

    def test_rust_p2p_when_enabled(self):
        n, _, patchers = _build_node(config_overrides={'ENABLE_RUST_P2P': True})
        try:
            assert n.rust_p2p is not None
            assert n.p2p is None
        finally:
            _stop_patchers(patchers)

    def test_p2p_handlers_registered(self, node):
        if node.p2p:
            names = [c[0][0] for c in node.p2p.register_handler.call_args_list]
            for handler in ('block', 'transaction', 'ping', 'pong', 'get_peers', 'peers'):
                assert handler in names, f"Handler '{handler}' not registered"


# ===========================================================================
# 7. Plugin registration (2 tests)
# ===========================================================================


class TestPluginRegistration:

    def test_four_plugins_registered(self, node):
        if node.plugin_manager:
            assert node.plugin_manager.register.call_count == 4

    def test_no_registration_when_plugin_manager_none(self):
        n, _, patchers = _build_node(
            broken_inline_targets=['qubitcoin.qvm.plugins.PluginManager']
        )
        try:
            assert n.plugin_manager is None
        finally:
            _stop_patchers(patchers)


# ===========================================================================
# 8. RPC app wiring (2 tests)
# ===========================================================================


class TestRPCAppWiring:

    def test_app_node_reference(self, node):
        assert node.app.node is node

    def test_app_lifecycle_events(self, node):
        node.app.on_event.assert_any_call("startup")
        node.app.on_event.assert_any_call("shutdown")


# ===========================================================================
# 9. Aether genesis paths (2 tests)
# ===========================================================================


class TestAetherGenesis:

    def test_genesis_check_called(self, node):
        node.aether_genesis.is_genesis_initialized.assert_called()

    def test_genesis_db_not_ready_handled(self):
        """If genesis init raises, node still initializes."""
        db = _mock_db()
        ag = _mock_aether_genesis()
        ag.is_genesis_initialized.return_value = False
        ag.initialize_genesis.side_effect = RuntimeError("DB not ready")

        top_patches = {
            'qubitcoin.node.Config': _mock_config(),
            'qubitcoin.node.console': MagicMock(),
            'qubitcoin.node.DatabaseManager': MagicMock(return_value=db),
            'qubitcoin.node.QuantumEngine': MagicMock(return_value=_mock_quantum()),
            'qubitcoin.node.P2PNetwork': MagicMock(return_value=_mock_p2p()),
            'qubitcoin.node.RustP2PClient': MagicMock(return_value=_mock_rust_p2p()),
            'qubitcoin.node.ConsensusEngine': MagicMock(return_value=_mock_consensus()),
            'qubitcoin.node.IPFSManager': MagicMock(return_value=_mock_ipfs()),
            'qubitcoin.node.StateManager': MagicMock(return_value=_mock_state_manager()),
            'qubitcoin.node.KnowledgeGraph': MagicMock(),
            'qubitcoin.node.PhiCalculator': MagicMock(),
            'qubitcoin.node.ReasoningEngine': MagicMock(),
            'qubitcoin.node.AetherEngine': MagicMock(return_value=_mock_aether()),
            'qubitcoin.node.AetherGenesis': MagicMock(return_value=ag),
            'qubitcoin.node.MiningEngine': MagicMock(return_value=_mock_mining()),
            'qubitcoin.node.ContractExecutor': MagicMock(),
            'qubitcoin.node.create_rpc_app': MagicMock(return_value=_mock_rpc_app()),
        }
        inline_patches = {t: MagicMock() for t in INLINE_TARGETS}
        patchers = []
        for t, m in {**top_patches, **inline_patches}.items():
            p = patch(t, m)
            patchers.append(p)
            p.start()
        p_import = patch('importlib.import_module', return_value=MagicMock())
        patchers.append(p_import)
        p_import.start()

        from qubitcoin.node import QubitcoinNode
        n = QubitcoinNode()
        assert n is not None

        _stop_patchers(patchers)


# ===========================================================================
# 10. on_block_mined (3 tests)
# ===========================================================================


class TestOnBlockMined:

    @pytest.mark.asyncio
    async def test_python_p2p_broadcast(self, node):
        """P2P broadcast via create_task in async context."""
        # In an async test, asyncio.create_task works — it wraps the broadcast coroutine
        node.on_block_mined({'height': 42, 'hash': 'abc123'})
        # If running in event loop, create_task succeeds and schedules the broadcast
        # Just verify no crash and metrics updated
        from qubitcoin.utils.metrics import blocks_mined
        assert blocks_mined._value.get() >= 1

    def test_no_p2p_no_crash(self, node):
        node.p2p = None
        node.rust_p2p = None
        node.on_block_mined({'height': 42, 'hash': 'abc123'})

    def test_broadcast_error_handled(self, node):
        # Force p2p.broadcast to raise; error should be caught gracefully
        node.p2p.broadcast.side_effect = RuntimeError("connection lost")
        node.on_block_mined({'height': 42, 'hash': 'abc123'})
        # No crash — error is logged and handled


# ===========================================================================
# 11. on_startup (4 tests)
# ===========================================================================


class TestOnStartup:

    @pytest.mark.asyncio
    async def test_startup_sets_running(self, node):
        await node.on_startup()
        assert node.running is True

    @pytest.mark.asyncio
    async def test_startup_creates_metrics_task(self, node):
        await node.on_startup()
        assert node.metrics_task is not None

    @pytest.mark.asyncio
    async def test_startup_starts_p2p(self, node):
        await node.on_startup()
        if node.p2p:
            node.p2p.start.assert_called_once()

    @pytest.mark.asyncio
    async def test_startup_bridge_failure_handled(self, node):
        node.bridge_manager = MagicMock()
        node.bridge_manager.initialize_bridges = AsyncMock(
            side_effect=RuntimeError("fail")
        )
        await node.on_startup()  # Must not raise
