"""
RPC Endpoints Extended Tests — Covers POST/PUT/DELETE and remaining GET endpoints
================================================================================

Supplements test_frontend_backend_integration.py (156 tests) with coverage for
mutation endpoints (POST/PUT/DELETE), wallet operations, staking, bridge actions,
compliance CRUD, debug/compile, and other untested endpoints.

Uses the same mock pattern: _SyncASGIClient, module-scoped fixtures, patched
inline-instantiated classes.
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

# Re-use mock factories and helpers from the existing test file
from tests.unit.test_frontend_backend_integration import (
    _make_db_manager,
    _make_consensus_engine,
    _make_mining_engine,
    _make_quantum_engine,
    _make_ipfs_manager,
    _make_aether_engine,
    _make_state_manager,
    _make_fee_collector,
    _make_pot_protocol,
    _make_bridge_manager,
    _make_stablecoin_engine,
    _make_plugin_manager,
    _make_compliance_engine,
    _make_mock_node,
    _MockChatSession,
    _SyncASGIClient,
    _PATCH_TARGETS,
    assert_shape,
)


# ---------------------------------------------------------------------------
# FIXTURES
# ---------------------------------------------------------------------------

@pytest.fixture(scope='module')
def app_and_client():
    """Create the FastAPI app with all mocks — extended fixture with extra wiring."""

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

    # Extra mock setup for extended endpoints
    # --- PoT task market ---
    mock_task = MagicMock()
    mock_task.task_id = 'task_001'
    mock_task.submitter = 'test_addr'
    mock_task.description = 'Test reasoning task'
    mock_task.query_type = 'general'
    mock_task.bounty_qbc = 5.0
    mock_task.status = MagicMock(value='open')
    mock_task.created_block = 50
    mock_task.claimed_by = None
    mock_task.solution_hash = None
    mock_task.validation_votes = []
    mock_task.reward_distributed = False
    pot.task_market.get_task = MagicMock(return_value=mock_task)
    pot.task_market.submit_task = MagicMock(return_value=mock_task)
    pot.validate_solution = MagicMock(return_value=True)

    # --- Contract engine ---
    contract_engine = MagicMock()
    contract_engine.deploy_contract.return_value = (True, 'Contract deployed', 'contract_001')
    contract_engine.execute.return_value = (True, 'Executed successfully', {'result': 42})

    # --- On-chain AGI ---
    on_chain_agi = MagicMock()
    on_chain_agi.get_onchain_phi.return_value = 0.42
    on_chain_agi.get_onchain_consciousness_status.return_value = {
        'phi': 0.42, 'is_conscious': False,
    }
    on_chain_agi.get_proof_by_block.return_value = 'proof_abc'
    on_chain_agi.get_principle_count.return_value = (10, 8)
    on_chain_agi.get_stats.return_value = {
        'blocks_published': 100, 'proofs_submitted': 90,
    }
    on_chain_agi.get_treasury_balance.return_value = 5000
    on_chain_agi.get_proposal_count.return_value = 3
    on_chain_agi.get_upgrade_proposal_count.return_value = 1

    # --- Bridge async methods ---
    bm.process_deposit = AsyncMock(return_value='0xdeposit_hash')
    bm.get_balance = AsyncMock(return_value=Decimal('100.0'))
    bm.estimate_fees = AsyncMock(return_value={
        'bridge_fee': '0.1', 'gas_estimate': '0.05',
    })
    bm.pause_bridge = AsyncMock()
    bm.resume_bridge = AsyncMock()

    # --- Stablecoin engine ---
    se.mint_qusd = MagicMock(return_value=(True, 'Minted 100 QUSD', 'vault_001'))
    se.burn_qusd = MagicMock(return_value=(True, 'Burned 50 QUSD'))

    # --- Plugin manager ---
    pm.start = MagicMock(return_value=True)
    pm.stop = MagicMock(return_value=True)
    gov_instance = MagicMock()
    gov_instance.list_proposals.return_value = []
    gov_proposal = MagicMock()
    gov_proposal.to_dict.return_value = {
        'id': 'prop_001', 'proposer': 'test', 'description': 'Test', 'type': 'general',
    }
    gov_instance.create_proposal.return_value = gov_proposal
    gov_instance.vote.return_value = True
    gov_meta = MagicMock()
    gov_meta.instance = gov_instance
    pm.registry.get = MagicMock(return_value=gov_meta)

    # --- Compliance engine ---
    mock_policy = MagicMock()
    mock_policy.to_dict.return_value = {
        'policy_id': 'pol_001', 'address': 'test_addr', 'kyc_level': 'basic',
    }
    comp.create_policy = MagicMock(return_value=mock_policy)
    comp.get_policy = MagicMock(return_value=mock_policy)
    comp.update_policy = MagicMock(return_value=mock_policy)
    comp.delete_policy = MagicMock(return_value=True)
    comp.reset_circuit_breaker = MagicMock()

    # --- TLAC manager ---
    tlac_mgr = MagicMock()
    tlac_mgr._transactions = {}  # Iterated directly for pending list
    tlac_mgr.create.return_value = {
        'success': True,
        'tlac_id': 'tlac_001',
        'transaction': {'tlac_id': 'tlac_001', 'initiator': 'test'},
    }

    # --- QVM debugger ---
    qvm_debugger = MagicMock()
    qvm_debugger.load_bytecode = MagicMock()
    qvm_debugger.step = MagicMock(return_value={
        'pc': 1, 'opcode': 'PUSH1', 'stack': [0], 'gas_used': 3,
    })
    qvm_debugger.get_stats = MagicMock(return_value={
        'pc': 0, 'stack': [], 'memory': '', 'gas_remaining': 30000000,
    })

    # --- QSol compiler ---
    qsol_compiler = MagicMock()
    qsol_compiler.compile = MagicMock(return_value={
        'bytecode': '6001', 'abi': [], 'warnings': [],
    })

    # --- State channel manager ---
    state_channel_mgr = MagicMock()
    state_channel_mgr.get_stats = MagicMock(return_value={'channels': []})
    mock_channel = MagicMock()
    mock_channel.to_dict.return_value = {
        'channel_id': 'ch_001', 'party_a': 'addr1', 'party_b': 'addr2', 'balance': '100',
    }
    state_channel_mgr.get_channel = MagicMock(return_value=mock_channel)

    # --- SPV verifier ---
    spv_verifier = MagicMock()
    spv_verifier.verify_merkle_proof = MagicMock(return_value=True)

    # --- IPFS memory ---
    ipfs_memory = MagicMock()
    ipfs_memory.get_stats = MagicMock(return_value={'cache_size': 0})
    ipfs_memory.store_memory = MagicMock(return_value='Qm_test_cid_123')
    ipfs_memory.retrieve_memory = MagicMock(return_value={
        'memory_id': 'mem_001', 'content': {'key': 'value'},
    })

    # --- Reserve verifier ---
    reserve_verifier = MagicMock()
    reserve_verifier.get_stats = MagicMock(return_value={'milestones': [], 'verified': True})

    # --- Knowledge graph mocks for subgraph/paths/prune/export ---
    mock_node_obj = MagicMock()
    mock_node_obj.to_dict.return_value = {
        'id': 1, 'content': 'test', 'node_type': 'assertion', 'confidence': 0.9,
    }
    ae.kg.get_subgraph = MagicMock(return_value={1: mock_node_obj})
    ae.kg.find_paths = MagicMock(return_value=[[1, 2, 3]])
    ae.kg.prune_low_confidence = MagicMock(return_value=5)
    ae.kg.export_json_ld = MagicMock(return_value={
        '@context': 'https://schema.org/', '@graph': [],
    })

    # --- LLM / knowledge seeder on mock node ---
    mock_node = _make_mock_node()
    mock_seeder = MagicMock()
    mock_seeder.seed_once = MagicMock(return_value={
        'nodes_created': 3, 'domain': 'physics',
    })
    mock_seeder.get_stats = MagicMock(return_value={'total_seeds': 10})
    mock_node.knowledge_seeder = mock_seeder

    # Build patchers for all inline-instantiated classes
    patchers = []
    mocks = {}
    for target in _PATCH_TARGETS:
        p = patch(target)
        patchers.append(p)

    for i, p in enumerate(patchers):
        m = p.start()
        target_name = _PATCH_TARGETS[i].split('.')[-1]
        mocks[target_name] = m

    # Configure key mock return values (same as base fixture)
    dashboard_inst = MagicMock()
    dashboard_inst.get_dashboard_data.return_value = {
        'status': {'is_conscious': False, 'phi': 0.42},
        'phi_history': [], 'events': [],
        'trend': {'trend': 'rising', 'slope': 0.01},
    }
    dashboard_inst.get_phi_history.return_value = []
    dashboard_inst.get_events.return_value = []
    dashboard_inst.event_count = 0
    dashboard_inst.get_trend.return_value = {
        'trend': 'stable', 'slope': 0.0, 'window_size': 20,
        'min_phi': 0.0, 'max_phi': 0.5, 'avg_phi': 0.2,
    }
    mocks['ConsciousnessDashboard'].return_value = dashboard_inst

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

    circ_inst = MagicMock()
    circ_inst.get_stats.return_value = {
        'current': None, 'halving_events': 0, 'snapshots_stored': 0,
        'total_fees_collected': '0',
    }
    circ_inst.get_emission_schedule.return_value = [
        {'era': 0, 'reward': 15.27, 'start_block': 0},
    ]
    mocks['CirculationTracker'].return_value = circ_inst

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

    pot_exp_inst = MagicMock()
    pot_exp_inst.get_block_thought.return_value = {
        'block_height': 10, 'thought_hash': 'abc', 'phi_value': 0.1,
        'reasoning_steps': [], 'knowledge_nodes_created': 2,
    }
    pot_exp_inst.get_block_range.return_value = []
    pot_exp_inst.get_phi_progression.return_value = [
        {'block_height': 1, 'phi': 0.01}, {'block_height': 2, 'phi': 0.02},
    ]
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

    report_inst = MagicMock()
    report_inst.get_stats.return_value = {
        'total_reports': 0, 'report_types': {},
        'compliance_engine_available': True, 'proof_store_available': True,
    }
    report_inst.list_reports.return_value = []
    mock_report = MagicMock()
    mock_report.to_dict.return_value = {
        'report_id': 'rpt_001', 'report_type': 'general', 'period': 'monthly',
        'generated_at': time.time(), 'data': {},
    }
    report_inst.generate_report.return_value = mock_report
    report_inst.get_report.return_value = {
        'report_id': 'rpt_001', 'report_type': 'general',
    }
    mocks['RegulatoryReportGenerator'].return_value = report_inst

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
    pool_inst.get_stats.return_value = {}
    pool_inst.get_history.return_value = []
    mocks['PoolHealthMonitor'].return_value = pool_inst

    sol_inst = MagicMock()
    sol_inst.get_stats.return_value = {
        'total_solutions': 5, 'verified_solutions': 3,
        'unverified_solutions': 2, 'total_verifications': 10,
        'total_confirmed': 3, 'avg_confidence': 0.95, 'unique_miners': 2,
    }
    sol_record = MagicMock()
    sol_record.to_dict.return_value = {
        'solution_id': 1, 'block_height': 10, 'energy': -0.5,
        'verifications': [], 'confirmed': False,
    }
    sol_inst.get_solution.return_value = sol_record
    sol_inst.get_by_block.return_value = sol_record
    sol_inst.get_top_verified.return_value = [sol_record]
    sol_inst.get_unverified.return_value = [sol_record]
    verification_result = MagicMock()
    verification_result.to_dict.return_value = {
        'solution_id': 1, 'verifier': 'test_addr', 'confirmed': True,
    }
    sol_inst.record_verification.return_value = verification_result
    mocks['SolutionVerificationTracker'].return_value = sol_inst

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
    }
    mocks['VQECapabilityDetector'].return_value = cap_inst

    snap_sched_inst = MagicMock()
    snap_sched_inst.get_stats.return_value = {
        'total_snapshots': 0, 'total_failures': 0,
        'last_snapshot_height': -1, 'interval_blocks': 1000,
        'history_size': 0, 'success_rate': 0.0,
    }
    snap_sched_inst.get_history.return_value = []
    snap_sched_inst.get_latest.return_value = None
    snap_record = MagicMock()
    snap_record.to_dict.return_value = {
        'height': 100, 'cid': 'Qm_snap', 'timestamp': time.time(),
    }
    snap_sched_inst.take_snapshot.return_value = snap_record
    mocks['SnapshotScheduler'].return_value = snap_sched_inst

    arch_inst = MagicMock()
    arch_inst.get_stats.return_value = {
        'total_archives': 0, 'total_solutions_archived': 0,
        'last_archive_height': -1, 'interval_blocks': 1000,
        'history_size': 0, 'cids_stored': 0,
    }
    arch_inst.get_history.return_value = []
    arch_inst.get_all_cids.return_value = []
    arch_record = MagicMock()
    arch_record.to_dict.return_value = {
        'from_height': 0, 'to_height': 100, 'cid': 'Qm_archive',
    }
    arch_inst.archive_range.return_value = arch_record
    mocks['SolutionArchiver'].return_value = arch_inst

    cap_adv_inst = MagicMock()
    cap_adv_inst.get_all_peers.return_value = []
    peer_cap = MagicMock()
    peer_cap.to_dict.return_value = {
        'peer_id': 'peer_1', 'backend_type': 'local', 'mining_power': 1.0,
    }
    cap_adv_inst.get_peers_by_power.return_value = [peer_cap]
    cap_adv_inst.get_network_summary.return_value = {
        'total_peers': 0, 'active_peers': 0, 'available_miners': 0,
    }
    cap_adv_inst.get_local_advertisement.return_value = {
        'type': 'capability_advertisement', 'backend_type': 'local_estimator',
    }
    cap_adv_inst.set_local_capability.return_value = None
    received_cap = MagicMock()
    received_cap.to_dict.return_value = {
        'peer_id': 'peer_x', 'backend_type': 'ibm_quantum',
    }
    cap_adv_inst.receive_advertisement.return_value = received_cap
    mocks['CapabilityAdvertiser'].return_value = cap_adv_inst

    comp_inst = MagicMock()
    comp_inst.list_policies.return_value = []
    comp_inst.check_compliance.return_value = 'basic'
    comp_inst.is_address_blocked.return_value = False
    comp_inst.circuit_breaker = MagicMock()
    comp_inst.circuit_breaker.to_dict.return_value = {'tripped': False, 'trip_count': 0}
    comp_inst.create_policy = comp.create_policy
    comp_inst.get_policy = comp.get_policy
    comp_inst.update_policy = comp.update_policy
    comp_inst.delete_policy = comp.delete_policy
    comp_inst.reset_circuit_breaker = comp.reset_circuit_breaker
    mocks['ComplianceEngine'].return_value = comp_inst

    proof_inst = MagicMock()
    proof_inst.get_stats.return_value = {
        'total_proofs': 0, 'unique_addresses': 0,
        'proof_types': {}, 'max_capacity': 50000,
    }
    mocks['ComplianceProofStore'].return_value = proof_inst

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

    fee_mgr_inst = MagicMock()
    fee_mgr_inst.get_fee_info.return_value = {
        'fee_qbc': '0.01', 'is_free': True, 'free_remaining': 5,
    }
    mocks['AetherFeeManager'].return_value = fee_mgr_inst

    fee_calc_inst = MagicMock()
    fee_calc_inst.calculate_deploy_fee.return_value = Decimal('1.5')
    mocks['ContractFeeCalculator'].return_value = fee_calc_inst

    # Sephirot manager for cognitive endpoints
    sephirot_mgr = MagicMock()
    sephirot_mgr.get_status = MagicMock(return_value={
        'keter': {'name': 'Keter', 'energy': 1.5},
    })

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
        contract_engine=contract_engine,
        state_manager=sm,
        aether_engine=ae,
        pot_protocol=pot,
        fee_collector=fc,
        qusd_oracle=MagicMock(),
        compliance_engine=comp,
        aml_monitor=MagicMock(get_alerts=MagicMock(return_value=[])),
        compliance_proof_store=proof_inst,
        tlac_manager=tlac_mgr,
        risk_normalizer=MagicMock(normalize=MagicMock(return_value=MagicMock(
            to_dict=MagicMock(return_value={'address': 'test', 'total_score': 0.1, 'risk_level': 'low'})
        ))),
        plugin_manager=pm,
        decoherence_manager=MagicMock(get_stats=MagicMock(return_value={'states': []})),
        transaction_batcher=MagicMock(get_stats=MagicMock(return_value={'pending': 0})),
        state_channel_manager=state_channel_mgr,
        qvm_debugger=qvm_debugger,
        qsol_compiler=qsol_compiler,
        systemic_risk_model=MagicMock(detect_high_risk_connections=MagicMock(return_value=[])),
        tx_graph=MagicMock(build_subgraph=MagicMock(return_value={})),
        stablecoin_engine=se,
        reserve_fee_router=MagicMock(get_stats=MagicMock(return_value={'inflows': []})),
        reserve_verifier=reserve_verifier,
        bridge_manager=bm,
        sephirot_manager=sephirot_mgr,
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
        spv_verifier=spv_verifier,
        ipfs_memory=ipfs_memory,
        capability_advertiser=cap_adv_inst,
        on_chain_agi=on_chain_agi,
    )

    # Set app.node for P2P + LLM endpoints
    app.node = mock_node

    client = _SyncASGIClient(app)

    yield app, client, {
        'db': db, 'ce': ce, 'me': me, 'qe': qe, 'ipfs': ipfs,
        'ae': ae, 'sm': sm, 'fc': fc, 'pot': pot, 'bm': bm,
        'se': se, 'pm': pm, 'comp': comp,
        'contract_engine': contract_engine,
        'on_chain_agi': on_chain_agi,
        'tlac_manager': tlac_mgr,
        'qvm_debugger': qvm_debugger,
        'qsol_compiler': qsol_compiler,
        'state_channel_mgr': state_channel_mgr,
        'spv_verifier': spv_verifier,
        'ipfs_memory': ipfs_memory,
        'reserve_verifier': reserve_verifier,
        'sephirot_mgr': sephirot_mgr,
        'mock_node': mock_node,
        'chat_session': chat_session,
        'mocks': mocks,
    }

    for p in patchers:
        p.stop()


# ---------------------------------------------------------------------------
# TEST CLASSES
# ---------------------------------------------------------------------------

class TestTransferEndpoint:
    """POST /transfer — bridge UTXO funds to account model."""

    _admin_headers = {'X-Admin-Key': _TEST_ADMIN_KEY}

    def test_transfer_no_auth(self, app_and_client):
        _, client, ctx = app_and_client
        resp = client.post("/transfer", json={'to': '0xabc123', 'amount': '10'})
        assert resp.status_code == 403

    def test_transfer_no_utxos(self, app_and_client):
        _, client, ctx = app_and_client
        # Session.execute().fetchall() returns [] by default → "No UTXOs available"
        resp = client.post("/transfer", json={'to': '0xabc123', 'amount': '10'},
                           headers=self._admin_headers)
        assert resp.status_code == 400
        assert 'No UTXOs' in resp.json().get('detail', '')

    def test_transfer_success(self, app_and_client):
        _, client, ctx = app_and_client
        # The endpoint now uses SELECT FOR UPDATE via session.execute(),
        # not db_manager.get_utxos().  Set up session mock accordingly.
        utxo_row = ('tx001', 0, '100')  # (txid, vout, amount) tuple
        call_count = [0]
        original_execute = ctx['db'].get_session().__enter__().execute

        def _execute_side_effect(*args, **kwargs):
            call_count[0] += 1
            result = MagicMock()
            if call_count[0] == 1:
                # First call: SELECT FOR UPDATE → return UTXO rows
                result.fetchall = MagicMock(return_value=[utxo_row])
            else:
                # Subsequent calls: UPDATE/INSERT → need rowcount=1
                result.rowcount = 1
                result.fetchall = MagicMock(return_value=[])
            return result

        with ctx['db'].get_session() as session:
            session.execute = MagicMock(side_effect=_execute_side_effect)

        resp = client.post("/transfer", json={'to': '0xabc123', 'amount': '10'},
                           headers=self._admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert 'tx_hash' in data
        assert 'from' in data
        assert 'to' in data
        assert 'amount' in data
        assert 'change' in data
        # Restore default execute behavior
        with ctx['db'].get_session() as session:
            exec_result = MagicMock()
            exec_result.scalar = MagicMock(return_value=0)
            exec_result.fetchall = MagicMock(return_value=[])
            exec_result.fetchone = MagicMock(return_value=None)
            session.execute = MagicMock(return_value=exec_result)

    def test_transfer_insufficient_balance(self, app_and_client):
        _, client, ctx = app_and_client
        # Return a UTXO with amount=5, but request 100 → "Insufficient"
        utxo_row = ('tx001', 0, '5')  # (txid, vout, amount) tuple

        def _execute_side_effect(*args, **kwargs):
            result = MagicMock()
            result.fetchall = MagicMock(return_value=[utxo_row])
            result.rowcount = 1
            return result

        with ctx['db'].get_session() as session:
            session.execute = MagicMock(side_effect=_execute_side_effect)

        resp = client.post("/transfer", json={'to': '0xabc123', 'amount': '100'},
                           headers=self._admin_headers)
        assert resp.status_code == 400
        assert 'Insufficient' in resp.json().get('detail', '')
        # Restore default execute behavior
        with ctx['db'].get_session() as session:
            exec_result = MagicMock()
            exec_result.scalar = MagicMock(return_value=0)
            exec_result.fetchall = MagicMock(return_value=[])
            exec_result.fetchone = MagicMock(return_value=None)
            session.execute = MagicMock(return_value=exec_result)


class TestWalletEndpoints:
    """POST /wallet/create, /wallet/send, /wallet/sign."""

    def test_wallet_create(self, app_and_client):
        _, client, _ = app_and_client
        with patch('qubitcoin.quantum.crypto.Dilithium2') as mock_dil:
            mock_dil.keygen.return_value = (b'\x01' * 32, b'\x02' * 64)
            mock_dil.derive_address.return_value = 'qbc1testaddr'
            resp = client.post("/wallet/create")
            assert resp.status_code == 200
            data = resp.json()
            assert 'address' in data
            assert 'public_key_hex' in data
            # FE-C1: private_key_hex is no longer returned for security
            assert 'private_key_hex' not in data
            assert '_notice' in data

    def test_wallet_sign(self, app_and_client):
        _, client, _ = app_and_client
        with patch('qubitcoin.quantum.crypto.DilithiumSigner') as mock_dil_cls, \
             patch('qubitcoin.quantum.crypto._sk_size_to_level') as mock_detect:
            from qubitcoin.quantum.crypto import SecurityLevel
            mock_detect.return_value = SecurityLevel.LEVEL2
            mock_dil_cls.return_value.sign.return_value = b'\xaa' * 2420
            resp = client.post("/wallet/sign", json={
                'message_hash': '00' * 32,
                'private_key_hex': 'ff' * 2528,  # Valid D2 sk hex length
            })
            assert resp.status_code == 200
            data = resp.json()
            assert 'signature_hex' in data

    def test_wallet_send_requires_valid_sig(self, app_and_client):
        _, client, ctx = app_and_client
        with patch('qubitcoin.quantum.crypto.Dilithium2') as mock_dil:
            mock_dil.derive_address.return_value = 'wrong_addr'
            resp = client.post("/wallet/send", json={
                'from_address': 'correct_addr',
                'to_address': 'dest_addr',
                'amount': '10',
                'signature_hex': 'aa' * 64,
                'public_key_hex': 'bb' * 32,
            })
            assert resp.status_code == 400
            assert 'does not match' in resp.json().get('detail', '')


class TestSephirotStakingEndpoints:
    """POST /sephirot/stake, /sephirot/unstake, /sephirot/claim-rewards."""

    def test_stake_invalid_node_id(self, app_and_client):
        _, client, _ = app_and_client
        with patch('qubitcoin.quantum.crypto.Dilithium2') as mock_dil:
            mock_dil.derive_address.return_value = 'test_addr'
            resp = client.post("/sephirot/stake", json={
                'address': 'test_addr',
                'node_id': 15,
                'amount': '100',
                'signature_hex': 'aa' * 64,
                'public_key_hex': 'bb' * 32,
            })
            assert resp.status_code == 400
            assert 'node_id' in resp.json().get('detail', '')

    def test_unstake_requires_valid_sig(self, app_and_client):
        _, client, _ = app_and_client
        with patch('qubitcoin.quantum.crypto.Dilithium2') as mock_dil:
            mock_dil.derive_address.return_value = 'wrong_addr'
            resp = client.post("/sephirot/unstake", json={
                'address': 'test_addr',
                'stake_id': 'stake_001',
                'signature_hex': 'aa' * 64,
                'public_key_hex': 'bb' * 32,
            })
            assert resp.status_code == 400
            assert 'does not match' in resp.json().get('detail', '')

    def test_claim_rewards_requires_valid_sig(self, app_and_client):
        _, client, _ = app_and_client
        with patch('qubitcoin.quantum.crypto.Dilithium2') as mock_dil:
            mock_dil.derive_address.return_value = 'wrong_addr'
            resp = client.post("/sephirot/claim-rewards", json={
                'address': 'test_addr',
                'signature_hex': 'aa' * 64,
                'public_key_hex': 'bb' * 32,
            })
            assert resp.status_code == 400


class TestPOTExtendedEndpoints:
    """GET /pot/task/{id}, POST /pot/submit-task, POST /pot/validate."""

    def test_pot_task_detail(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/pot/task/task_001")
        assert resp.status_code == 200
        data = resp.json()
        assert data['task_id'] == 'task_001'
        assert 'bounty_qbc' in data
        assert 'status' in data
        assert 'votes' in data

    def test_pot_task_not_found(self, app_and_client):
        _, client, ctx = app_and_client
        ctx['pot'].task_market.get_task.return_value = None
        resp = client.get("/pot/task/nonexistent")
        assert resp.status_code == 404
        # Restore
        mock_task = MagicMock()
        mock_task.task_id = 'task_001'
        mock_task.submitter = 'test_addr'
        mock_task.description = 'Test reasoning task'
        mock_task.query_type = 'general'
        mock_task.bounty_qbc = 5.0
        mock_task.status = MagicMock(value='open')
        mock_task.created_block = 50
        mock_task.claimed_by = None
        mock_task.solution_hash = None
        mock_task.validation_votes = []
        mock_task.reward_distributed = False
        ctx['pot'].task_market.get_task.return_value = mock_task

    def test_pot_submit_task(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.post("/pot/submit-task", json={
            'submitter': 'test_addr',
            'description': 'What is the nature of gravity?',
            'bounty_qbc': 5.0,
            'query_type': 'general',
        })
        assert resp.status_code == 200
        data = resp.json()
        assert 'task_id' in data
        assert 'bounty_qbc' in data
        assert 'status' in data

    def test_pot_validate(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.post("/pot/validate", json={
            'task_id': 'task_001',
            'validator_address': 'validator_addr',
            'approve': True,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data['task_id'] == 'task_001'
        assert data['approve'] is True


class TestP2PConnectEndpoint:
    """POST /p2p/connect."""

    def test_p2p_connect(self, app_and_client):
        _, client, ctx = app_and_client
        # connect_to_peer is awaited in the endpoint — must be AsyncMock
        ctx['mock_node'].p2p.connect_to_peer = AsyncMock()
        resp = client.post("/p2p/connect?address=192.168.1.1:4001")
        assert resp.status_code == 200
        data = resp.json()
        assert data['status'] == 'success'


class TestContractEndpoints:
    """POST /contracts/deploy, /contracts/execute, GET /contracts, /contracts/{id}."""

    def test_contracts_deploy(self, app_and_client):
        _, client, ctx = app_and_client
        # collect_fee must return (success, message, fee_record) tuple
        fee_rec = MagicMock()
        fee_rec.fee_amount = Decimal('1.5')
        ctx['fc'].collect_fee = MagicMock(return_value=(True, 'Fee collected', fee_rec))
        resp = client.post("/contracts/deploy", json={
            'contract_type': 'token',
            'contract_code': {'name': 'TestToken', 'symbol': 'TT', 'supply': 1000},
            'deployer': 'deployer_addr',
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data['success'] is True
        assert 'contract_id' in data
        assert 'deployer' in data

    def test_contracts_execute(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.post("/contracts/execute", json={
            'contract_id': 'contract_001',
            'function': 'transfer',
            'args': {'to': 'addr2', 'amount': 100},
            'caller': 'addr1',
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data['success'] is True
        assert 'result' in data

    def test_contracts_list(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/contracts")
        assert resp.status_code == 200
        data = resp.json()
        assert 'contracts' in data
        assert 'total' in data

    def test_contracts_get_by_id(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/contracts/contract_001")
        # Could be 200 (found) or 404 (mock DB returns no rows)
        assert resp.status_code in (200, 404)


class TestQVMCallEndpoint:
    """POST /qvm/call — static contract call."""

    def test_qvm_call_success(self, app_and_client):
        _, client, ctx = app_and_client
        ctx['sm'].qvm.static_call.return_value = b'\x00' * 32
        resp = client.post("/qvm/call", json={
            'contract_address': '0x' + 'ab' * 20,
            'calldata': '0x70a08231' + '00' * 32,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data['success'] is True
        assert 'result' in data

    def test_qvm_call_invalid_calldata(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.post("/qvm/call", json={
            'contract_address': '0xtest',
            'calldata': 'not_hex!!!',
        })
        assert resp.status_code == 400


class TestQVMNFTsAndEvents:
    """GET /qvm/nfts/{address}, /qvm/events/{address}."""

    def test_nfts_empty(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/qvm/nfts/test_addr")
        assert resp.status_code == 200
        data = resp.json()
        assert 'nfts' in data
        assert 'total' in data
        assert isinstance(data['nfts'], list)

    def test_events_empty(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/qvm/events/test_addr")
        assert resp.status_code == 200
        data = resp.json()
        assert 'events' in data
        assert 'total' in data
        assert 'limit' in data
        assert 'offset' in data


class TestQVMDebugAndCompile:
    """POST /qvm/debug/load, /qvm/debug/step, GET /qvm/debug/state, POST /qvm/compile."""

    def test_debug_load(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.post("/qvm/debug/load", json={'bytecode': '600160005260206000f3'})
        assert resp.status_code == 200
        data = resp.json()
        assert data['loaded'] is True
        assert 'bytecode_size' in data

    def test_debug_step(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.post("/qvm/debug/step")
        assert resp.status_code == 200
        data = resp.json()
        assert 'pc' in data
        assert 'opcode' in data

    def test_debug_state(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/qvm/debug/state")
        assert resp.status_code == 200
        data = resp.json()
        assert 'pc' in data
        assert 'stack' in data

    def test_compile(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.post("/qvm/compile", json={
            'source': 'contract Test { function hello() public pure returns (uint) { return 1; } }',
        })
        assert resp.status_code == 200
        data = resp.json()
        assert 'bytecode' in data


class TestBridgeExtendedEndpoints:
    """POST /bridge/deposit, GET /bridge/balance, /bridge/fees, POST /bridge/pause, /bridge/resume."""

    def test_bridge_deposit(self, app_and_client):
        _, client, _ = app_and_client
        with patch('qubitcoin.bridge.base.ChainType') as mock_ct:
            mock_ct.return_value = 'ethereum'
            resp = client.post("/bridge/deposit", json={
                'chain': 'ethereum',
                'qbc_txid': 'tx_001',
                'qbc_address': 'qbc_addr',
                'target_address': '0xeth_addr',
                'amount': '100',
            })
            assert resp.status_code == 200
            data = resp.json()
            assert 'tx_hash' in data
            assert 'chain' in data
            assert 'amount' in data

    def test_bridge_balance(self, app_and_client):
        _, client, _ = app_and_client
        with patch('qubitcoin.bridge.base.ChainType') as mock_ct:
            mock_ct.return_value = 'ethereum'
            resp = client.get("/bridge/balance/ethereum/0xtest_addr")
            assert resp.status_code == 200
            data = resp.json()
            assert 'balance' in data
            assert 'chain' in data

    def test_bridge_fees(self, app_and_client):
        _, client, _ = app_and_client
        with patch('qubitcoin.bridge.base.ChainType') as mock_ct:
            mock_ct.return_value = 'ethereum'
            resp = client.get("/bridge/fees/ethereum/100")
            assert resp.status_code == 200

    def test_bridge_pause(self, app_and_client):
        _, client, _ = app_and_client
        with patch('qubitcoin.bridge.base.ChainType') as mock_ct:
            mock_ct.return_value = 'ethereum'
            resp = client.post("/bridge/pause/ethereum")
            assert resp.status_code == 200
            data = resp.json()
            assert data['paused'] is True

    def test_bridge_resume(self, app_and_client):
        _, client, _ = app_and_client
        with patch('qubitcoin.bridge.base.ChainType') as mock_ct:
            mock_ct.return_value = 'ethereum'
            resp = client.post("/bridge/resume/ethereum")
            assert resp.status_code == 200
            data = resp.json()
            assert data['resumed'] is True


class TestPrivacyExtendedEndpoints:
    """POST /privacy/range-proof/verify, /privacy/stealth/create-output, /privacy/tx/build."""

    def test_range_proof_verify(self, app_and_client):
        _, client, _ = app_and_client
        with patch('qubitcoin.privacy.range_proofs.RangeProofGenerator') as mock_rp:
            inst = MagicMock()
            inst.verify.return_value = True
            mock_rp.return_value = inst
            resp = client.post("/privacy/range-proof/verify", json={
                'proof': {'commitment': 'abc', 'data': 'def'},
            })
            assert resp.status_code == 200
            data = resp.json()
            assert 'valid' in data

    def test_stealth_create_output(self, app_and_client):
        _, client, _ = app_and_client
        # Generate real keypair to get valid compressed EC points
        from qubitcoin.privacy.stealth import StealthAddressManager
        kp = StealthAddressManager.generate_keypair()
        def compress(p):
            prefix = b'\x02' if p.y % 2 == 0 else b'\x03'
            return (prefix + p.x.to_bytes(32, 'big')).hex()
        resp = client.post("/privacy/stealth/create-output", json={
            'recipient_spend_pub': compress(kp.spend_pubkey),
            'recipient_view_pub': compress(kp.view_pubkey),
        })
        assert resp.status_code == 200
        data = resp.json()
        assert 'one_time_address' in data
        assert 'ephemeral_pubkey' in data

    def test_privacy_tx_build(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.post("/privacy/tx/build", json={
            'inputs': [{'txid': 'a' * 64, 'vout': 0, 'value': 100000, 'blinding': 12345, 'spending_key': 67890}],
            'outputs': [{'value': 90000}],
            'fee_atoms': 10000,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert 'tx_type' in data
        assert data['tx_type'] == 'susy_swap'
        assert data['is_private'] is True


class TestPluginExtendedEndpoints:
    """POST /qvm/plugins/{name}/start, stop, governance/propose, governance/vote."""

    def test_plugin_start(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.post("/qvm/plugins/PrivacyPlugin/start")
        assert resp.status_code == 200
        data = resp.json()
        assert data['started'] is True

    def test_plugin_stop(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.post("/qvm/plugins/PrivacyPlugin/stop")
        assert resp.status_code == 200
        data = resp.json()
        assert data['stopped'] is True

    def test_governance_propose(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.post("/qvm/plugins/governance/propose", json={
            'proposer': 'test_addr',
            'description': 'Increase block gas limit',
            'type': 'parameter_change',
        })
        assert resp.status_code == 200
        data = resp.json()
        assert 'id' in data or 'proposer' in data

    def test_governance_vote(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.post("/qvm/plugins/governance/vote", json={
            'proposal_id': 'prop_001',
            'voter': 'voter_addr',
            'approve': True,
            'weight': 1.0,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data['voted'] is True


class TestComplianceCRUDEndpoints:
    """POST/PUT/DELETE /qvm/compliance/policies, circuit-breaker/reset, reports/generate, tlac/create."""

    def test_create_policy(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.post("/qvm/compliance/policies", json={
            'address': 'test_addr',
            'kyc_level': 'basic',
            'daily_limit': 10000.0,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert 'policy' in data

    def test_get_policy_by_id(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/qvm/compliance/policies/pol_001")
        assert resp.status_code == 200
        data = resp.json()
        assert 'policy' in data

    def test_update_policy(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.put("/qvm/compliance/policies/pol_001", json={
            'daily_limit': 20000.0,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert 'policy' in data

    def test_delete_policy(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.delete("/qvm/compliance/policies/pol_001")
        assert resp.status_code == 200
        data = resp.json()
        assert data['deleted'] is True

    def test_delete_policy_not_found(self, app_and_client):
        _, client, ctx = app_and_client
        ctx['comp'].delete_policy.return_value = False
        resp = client.delete("/qvm/compliance/policies/nonexistent")
        assert resp.status_code == 404
        ctx['comp'].delete_policy.return_value = True  # restore

    def test_circuit_breaker_reset(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.post("/qvm/compliance/circuit-breaker/reset")
        assert resp.status_code == 200
        data = resp.json()
        assert data['reset'] is True

    def test_generate_report(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.post("/qvm/compliance/reports/generate", json={
            'report_type': 'general',
            'period': 'monthly',
        })
        assert resp.status_code == 200
        data = resp.json()
        assert 'report_id' in data

    def test_get_report_by_id(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/qvm/compliance/reports/rpt_001")
        assert resp.status_code == 200
        data = resp.json()
        assert 'report_id' in data

    def test_tlac_create(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.post("/qvm/compliance/tlac/create", json={
            'sender': 'addr1',
            'recipient': 'addr2',
            'amount': 1000,
            'jurisdictions': ['US', 'EU'],
            'timeout_blocks': 100,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data.get('success') is True
        assert 'tlac_id' in data


class TestSUSYVerificationEndpoints:
    """GET/POST /susy-database/verifications/*."""

    def test_verification_by_solution_id(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/susy-database/verifications/1")
        assert resp.status_code == 200
        data = resp.json()
        assert 'solution_id' in data

    def test_verification_by_block(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/susy-database/verifications/block/10")
        assert resp.status_code == 200
        data = resp.json()
        assert 'solution_id' in data

    def test_top_verified(self, app_and_client):
        """NOTE: /susy-database/verifications/top returns 422 because the
        parameterized route /susy-database/verifications/{solution_id} (int)
        is registered before this literal route in rpc.py. FastAPI matches
        'top' as solution_id and fails int validation. This is a known
        route-ordering issue."""
        _, client, _ = app_and_client
        resp = client.get("/susy-database/verifications/top?limit=5")
        # Route ordering bug: 'top' matches {solution_id} int param -> 422
        assert resp.status_code == 422

    def test_unverified(self, app_and_client):
        """Same route ordering issue as test_top_verified — 'unverified'
        matches the {solution_id} int parameter."""
        _, client, _ = app_and_client
        resp = client.get("/susy-database/verifications/unverified?limit=5")
        assert resp.status_code == 422

    def test_submit_verification(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.post("/susy-database/verifications/1/verify", json={
            'verifier_address': 'verifier_addr',
            'verified_energy': -0.5,
            'energy_tolerance': 0.01,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert 'solution_id' in data

    def test_submit_verification_missing_verifier(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.post("/susy-database/verifications/1/verify", json={
            'verified_energy': -0.5,
        })
        assert resp.status_code == 400


class TestSnapshotAndArchiveTriggers:
    """POST /snapshots/trigger, /susy-database/archives/trigger."""

    def test_snapshot_trigger(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.post("/snapshots/trigger")
        assert resp.status_code == 200
        data = resp.json()
        assert 'height' in data

    def test_archive_trigger(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.post("/susy-database/archives/trigger")
        assert resp.status_code == 200
        data = resp.json()
        assert 'from_height' in data
        assert 'to_height' in data

    def test_archive_history(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/susy-database/archives/history")
        assert resp.status_code == 200
        data = resp.json()
        assert 'history' in data


class TestKnowledgeGraphExtended:
    """GET /aether/knowledge/subgraph, /paths, /export, POST /prune."""

    def test_knowledge_subgraph(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/aether/knowledge/subgraph/1?depth=2")
        assert resp.status_code == 200
        data = resp.json()
        assert data['root_id'] == 1
        assert 'nodes' in data
        assert 'count' in data

    def test_knowledge_paths(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/aether/knowledge/paths/1/3?max_depth=5")
        assert resp.status_code == 200
        data = resp.json()
        assert 'paths' in data
        assert 'count' in data

    def test_knowledge_prune(self, app_and_client):
        _, client, _ = app_and_client
        # L1-H10: knowledge_prune now requires admin auth
        resp = client.post("/aether/knowledge/prune?threshold=0.1")
        assert resp.status_code == 403  # No auth provided
        # With valid admin key
        import os
        admin_key = os.getenv("ADMIN_API_KEY", "")
        if admin_key:
            resp = client.post(
                "/aether/knowledge/prune?threshold=0.1",
                headers={"X-Admin-Key": admin_key},
            )
            assert resp.status_code == 200

    def test_knowledge_prune_bad_threshold(self, app_and_client):
        _, client, _ = app_and_client
        # L1-H10: now returns 403 (auth required) before checking threshold
        resp = client.post("/aether/knowledge/prune?threshold=0.9")
        assert resp.status_code == 403

    def test_knowledge_export(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/aether/knowledge/export?format=json-ld")
        assert resp.status_code == 200
        data = resp.json()
        assert '@context' in data or '@graph' in data


class TestOnChainAGIEndpoints:
    """GET /aether/on-chain/*."""

    def test_onchain_phi(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/aether/on-chain/phi")
        assert resp.status_code == 200
        data = resp.json()
        assert 'phi' in data
        assert data['source'] == 'on-chain'

    def test_onchain_consciousness(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/aether/on-chain/consciousness")
        assert resp.status_code == 200
        data = resp.json()
        assert 'phi' in data

    def test_onchain_proof(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/aether/on-chain/proof/10")
        assert resp.status_code == 200
        data = resp.json()
        assert data['block_height'] == 10
        assert 'proof_id' in data
        assert 'exists' in data

    def test_onchain_constitution(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/aether/on-chain/constitution")
        assert resp.status_code == 200
        data = resp.json()
        assert 'total_principles' in data
        assert 'active_principles' in data

    def test_onchain_stats(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/aether/on-chain/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert 'blocks_published' in data


class TestGovernanceEndpoints:
    """GET /governance/treasury/balance, /governance/proposals/count."""

    def test_treasury_balance(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/governance/treasury/balance")
        assert resp.status_code == 200
        data = resp.json()
        assert 'balance' in data
        assert data['source'] == 'on-chain'

    def test_proposals_count(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/governance/proposals/count")
        assert resp.status_code == 200
        data = resp.json()
        assert 'treasury_proposals' in data
        assert 'upgrade_proposals' in data


class TestLLMSeedEndpoints:
    """POST /aether/llm/seed, /aether/llm/seed-batch, /aether/llm/seed-user."""

    def test_llm_seed(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.post("/aether/llm/seed")
        assert resp.status_code == 200
        data = resp.json()
        assert data['status'] == 'ok'
        assert 'nodes_created' in data

    def test_llm_seed_batch(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.post("/aether/llm/seed-batch?count=3")
        assert resp.status_code == 200
        data = resp.json()
        assert 'seeded' in data
        assert 'total_requested' in data

    def test_llm_seed_user_bad_key(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.post("/aether/llm/seed-user", json={
            'wallet_address': 'test_addr',
            'api_key': 'bad_key',
            'prompt': 'Tell me about quantum computing',
        })
        assert resp.status_code == 400
        assert 'Invalid API key' in resp.json().get('detail', '')

    def test_llm_seed_user_short_prompt(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.post("/aether/llm/seed-user", json={
            'wallet_address': 'test_addr',
            'api_key': 'sk-validkey123',
            'prompt': 'short',
        })
        assert resp.status_code == 400
        assert 'at least 10' in resp.json().get('detail', '')


class TestCognitiveExtendedEndpoints:
    """GET /aether/cognitive/sephirot/{role}, POST pineal/tick, safety/evaluate."""

    def test_cognitive_sephirot_by_role(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/aether/cognitive/sephirot/keter")
        assert resp.status_code == 200
        data = resp.json()
        assert 'name' in data

    def test_cognitive_sephirot_role_not_found(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/aether/cognitive/sephirot/nonexistent_role")
        assert resp.status_code == 404

    def test_cognitive_pineal_tick(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.post("/aether/cognitive/pineal/tick", json={
            'block_height': 100,
            'phi_value': 0.5,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert 'phase' in data
        assert 'metabolic_rate' in data

    def test_cognitive_safety_evaluate(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.post("/aether/cognitive/safety/evaluate", json={
            'action': 'Transfer 1000 QBC to unknown address',
            'source_node': 'chesed',
            'target_node': 'malkuth',
            'block_height': 100,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert 'allowed' in data


class TestLightNodeEndpoints:
    """POST /light/verify-tx."""

    def test_light_verify_tx(self, app_and_client):
        _, client, _ = app_and_client
        with patch('qubitcoin.network.light_node.MerkleProof') as mock_mp:
            mock_mp.return_value = MagicMock()
            resp = client.post("/light/verify-tx", json={
                'tx_hash': 'abc123',
                'merkle_root': 'root123',
                'siblings': ['sib1', 'sib2'],
                'index': 0,
                'block_height': 10,
            })
            assert resp.status_code == 200
            data = resp.json()
            assert 'valid' in data
            assert 'tx_hash' in data


class TestIPFSMemoryEndpoints:
    """POST /aether/memory/store, GET /aether/memory/{cid}."""

    def test_memory_store(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.post("/aether/memory/store", json={
            'memory_id': 'mem_001',
            'memory_type': 'episodic',
            'content': {'event': 'genesis'},
            'source_block': 0,
            'confidence': 1.0,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert 'cid' in data

    def test_memory_retrieve(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/aether/memory/Qm_test_cid_123")
        assert resp.status_code == 200
        data = resp.json()
        assert 'memory_id' in data

    def test_memory_retrieve_not_found(self, app_and_client):
        _, client, ctx = app_and_client
        ctx['ipfs_memory'].retrieve_memory.return_value = None
        resp = client.get("/aether/memory/Qm_nonexistent")
        assert resp.status_code == 404
        ctx['ipfs_memory'].retrieve_memory.return_value = {
            'memory_id': 'mem_001', 'content': {'key': 'value'},
        }  # restore


class TestQVMTokenExtended:
    """GET /qvm/tokens/list, /qvm/tokens/balances/{address}."""

    def test_tokens_list(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/qvm/tokens/list")
        assert resp.status_code == 200
        data = resp.json()
        assert 'tokens' in data

    def test_token_balances(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/qvm/tokens/balances/test_addr")
        assert resp.status_code == 200
        data = resp.json()
        assert 'address' in data
        assert 'tokens' in data


class TestQVMChannelDetail:
    """GET /qvm/channels/{channel_id}."""

    def test_channel_found(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/qvm/channels/ch_001")
        assert resp.status_code == 200
        data = resp.json()
        assert 'channel_id' in data

    def test_channel_not_found(self, app_and_client):
        _, client, ctx = app_and_client
        ctx['state_channel_mgr'].get_channel.return_value = None
        resp = client.get("/qvm/channels/ch_nonexistent")
        assert resp.status_code == 404
        # restore
        mock_ch = MagicMock()
        mock_ch.to_dict.return_value = {
            'channel_id': 'ch_001', 'party_a': 'a', 'party_b': 'b', 'balance': '100',
        }
        ctx['state_channel_mgr'].get_channel.return_value = mock_ch


class TestQUSDExtendedEndpoints:
    """GET /qusd/vaults/at-risk, POST /qusd/mint, /qusd/burn, GET /qusd/reserves/verification."""

    def test_vaults_at_risk(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/qusd/vaults/at-risk")
        assert resp.status_code == 200
        data = resp.json()
        assert 'vaults' in data

    def test_qusd_mint(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.post("/qusd/mint", json={
            'user_address': 'test_addr',
            'collateral_amount': '500',
            'collateral_type': 'QBC',
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data['success'] is True
        assert 'vault_id' in data

    def test_qusd_burn(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.post("/qusd/burn", json={
            'user_address': 'test_addr',
            'amount': '50',
            'vault_id': 'vault_001',
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data['success'] is True

    def test_qusd_reserves_verification(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/qusd/reserves/verification")
        assert resp.status_code == 200
        data = resp.json()
        assert 'verified' in data or 'milestones' in data


class TestCirculationEmissionSchedule:
    """GET /circulation/emission-schedule."""

    def test_emission_schedule(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/circulation/emission-schedule?num_eras=5")
        assert resp.status_code == 200
        data = resp.json()
        assert 'schedule' in data
        assert isinstance(data['schedule'], list)


class TestFeeEstimateEndpoint:
    """GET /fee-estimate — transaction fee estimation."""

    def test_fee_estimate_returns_tiers(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/fee-estimate")
        assert resp.status_code == 200
        data = resp.json()
        assert 'low' in data
        assert 'medium' in data
        assert 'high' in data
        assert 'mempool_size' in data
        assert 'min_fee' in data
        assert data['unit'] == 'QBC'

    def test_fee_estimate_low_le_medium_le_high(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/fee-estimate")
        data = resp.json()
        assert data['low'] <= data['medium'] <= data['high']

    def test_fee_estimate_above_min_fee(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/fee-estimate")
        data = resp.json()
        assert data['low'] >= data['min_fee']
        assert data['medium'] >= data['min_fee']


class TestInflationEndpoint:
    """GET /inflation — current inflation rate and supply metrics."""

    def test_inflation_returns_fields(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/inflation")
        assert resp.status_code == 200
        data = resp.json()
        assert 'current_height' in data
        assert 'total_supply' in data
        assert 'max_supply' in data
        assert 'current_block_reward' in data
        assert 'annual_emission_estimate' in data
        assert 'inflation_rate_percent' in data
        assert 'blocks_per_year' in data

    def test_inflation_rate_non_negative(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/inflation")
        data = resp.json()
        assert data['inflation_rate_percent'] >= 0

    def test_inflation_max_supply_matches_config(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/inflation")
        data = resp.json()
        from qubitcoin.config import Config
        assert data['max_supply'] == float(Config.MAX_SUPPLY)


class TestTokenHoldersTransfersBalance:
    """GET /tokens/{addr}/holders, /tokens/{addr}/transfers, /tokens/{addr}/balance/{holder}, /address/{addr}/tokens."""

    def test_token_holders(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/tokens/0xtoken_addr/holders")
        assert resp.status_code == 200
        data = resp.json()
        assert 'holders' in data

    def test_token_transfers(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/tokens/0xtoken_addr/transfers")
        assert resp.status_code == 200
        data = resp.json()
        assert 'transfers' in data

    def test_token_balance_for_holder(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/tokens/0xtoken_addr/balance/0xholder_addr")
        assert resp.status_code == 200
        data = resp.json()
        assert 'balance' in data
        assert 'token' in data
        assert 'holder' in data

    def test_address_tokens(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/address/test_addr/tokens")
        assert resp.status_code == 200
        data = resp.json()
        assert 'transfers' in data


class TestPOTExplorerExtended:
    """GET /aether/pot/phi-progression, consciousness-events, range, summary."""

    def test_phi_progression(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/aether/pot/phi-progression")
        assert resp.status_code == 200

    def test_consciousness_events(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/aether/pot/consciousness-events")
        assert resp.status_code == 200

    def test_pot_range(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/aether/pot/range/0/10")
        assert resp.status_code == 200

    def test_pot_summary(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/aether/pot/summary/10")
        assert resp.status_code == 200
        data = resp.json()
        assert 'block_height' in data


class TestP2PCapabilitiesExtended:
    """GET /p2p/capabilities/ranked, POST /p2p/capabilities/report."""

    def test_capabilities_ranked(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.get("/p2p/capabilities/ranked?limit=5")
        assert resp.status_code == 200
        data = resp.json()
        assert 'peers' in data
        assert isinstance(data['peers'], list)

    def test_capabilities_report(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.post("/p2p/capabilities/report", json={
            'peer_id': 'peer_x',
            'backend_type': 'ibm_quantum',
            'max_qubits': 127,
            'is_simulator': False,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert 'peer_id' in data

    def test_capabilities_report_no_peer_id(self, app_and_client):
        _, client, _ = app_and_client
        resp = client.post("/p2p/capabilities/report", json={
            'backend_type': 'ibm_quantum',
        })
        assert resp.status_code == 400
