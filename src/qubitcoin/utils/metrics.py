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
total_fees_burned_metric = Gauge('qbc_total_fees_burned', 'Total QBC burned from transaction fees')

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

# ============================================================================
# BRIDGE METRICS
# ============================================================================
bridge_active_chains = Gauge('qbc_bridge_active_chains', 'Number of active bridge chains')
bridge_deposits_total = Counter('qbc_bridge_deposits_total', 'Total bridge deposits')
bridge_withdrawals_total = Counter('qbc_bridge_withdrawals_total', 'Total bridge withdrawals')
bridge_tvl = Gauge('qbc_bridge_tvl', 'Total value locked across all bridges')

# ============================================================================
# PRIVACY METRICS
# ============================================================================
privacy_commitments_created = Counter('qbc_privacy_commitments_created_total', 'Pedersen commitments created')
privacy_range_proofs_generated = Counter('qbc_privacy_range_proofs_generated_total', 'Bulletproof range proofs generated')
privacy_stealth_outputs_created = Counter('qbc_privacy_stealth_outputs_created_total', 'Stealth address outputs created')

# ============================================================================
# COMPLIANCE METRICS
# ============================================================================
compliance_policies_total = Gauge('qbc_compliance_policies_total', 'Total compliance policies')
compliance_blocked_addresses = Gauge('qbc_compliance_blocked_addresses', 'Number of blocked addresses')
compliance_circuit_breaker = Gauge('qbc_compliance_circuit_breaker', 'Circuit breaker status (0=closed, 1=open)')
aml_alerts_total = Counter('qbc_aml_alerts_total', 'Total AML alerts raised')
sanctions_entries_total = Gauge('qbc_sanctions_entries_total', 'Total sanctions list entries')

# ============================================================================
# PLUGIN METRICS
# ============================================================================
qvm_plugins_registered = Gauge('qbc_qvm_plugins_registered', 'Total registered QVM plugins')
qvm_plugins_active = Gauge('qbc_qvm_plugins_active', 'Currently active QVM plugins')

# ============================================================================
# QVM EXTENSION METRICS
# ============================================================================
qvm_state_channels_open = Gauge('qbc_qvm_state_channels_open', 'Open state channels')
qvm_state_channels_tvl = Gauge('qbc_qvm_state_channels_tvl', 'TVL in state channels')
qvm_batch_pending_txs = Gauge('qbc_qvm_batch_pending_txs', 'Pending batched transactions')
qvm_decoherence_active = Gauge('qbc_qvm_decoherence_active', 'Active decoherence-tracked states')
qvm_token_transfers_total = Counter('qbc_qvm_token_transfers_total', 'Total token transfers tracked')
tlac_pending = Gauge('qbc_tlac_pending', 'Pending TLAC transactions')

# ============================================================================
# STABLECOIN METRICS
# ============================================================================
qusd_total_supply = Gauge('qbc_qusd_total_supply', 'QUSD total supply')
qusd_reserve_backing_pct = Gauge('qbc_qusd_reserve_backing_pct', 'QUSD reserve backing percentage')
qusd_active_vaults = Gauge('qbc_qusd_active_vaults', 'Active QUSD vaults')
qusd_total_debt = Gauge('qbc_qusd_total_debt', 'Total QUSD debt outstanding')

# ============================================================================
# COGNITIVE ARCHITECTURE METRICS
# ============================================================================
sephirot_active_nodes = Gauge('qbc_sephirot_active_nodes', 'Active Sephirot nodes')
sephirot_susy_violations_total = Counter('qbc_sephirot_susy_violations_total', 'Total SUSY balance violations')
sephirot_susy_corrections_total = Counter('qbc_sephirot_susy_corrections_total', 'Total SUSY balance corrections applied')
csf_messages_delivered_total = Counter('qbc_csf_messages_delivered_total', 'CSF messages delivered')
csf_queue_depth = Gauge('qbc_csf_queue_depth', 'CSF message queue depth')
pineal_current_phase = Gauge('qbc_pineal_current_phase', 'Current circadian phase (0-5)')
pineal_metabolic_rate = Gauge('qbc_pineal_metabolic_rate', 'Current metabolic rate')
pineal_is_conscious = Gauge('qbc_pineal_is_conscious', 'Consciousness flag (0/1)')
safety_vetoes_total = Counter('qbc_safety_vetoes_total', 'Total safety vetoes (Gevurah)')
safety_evaluations_total = Counter('qbc_safety_evaluations_total', 'Total safety evaluations')

# ============================================================================
# HIGGS COGNITIVE FIELD METRICS
# ============================================================================
higgs_field_value = Gauge('qbc_higgs_field_value', 'Current Higgs field value')
higgs_vev = Gauge('qbc_higgs_vev', 'Higgs vacuum expectation value')
higgs_deviation_pct = Gauge('qbc_higgs_deviation_pct', 'Higgs field deviation from VEV (%)')
higgs_mass_gap = Gauge('qbc_higgs_mass_gap', 'SUSY mass gap metric')
higgs_excitations_total = Counter('qbc_higgs_excitations_total', 'Total Higgs excitation events')
higgs_avg_cognitive_mass = Gauge('qbc_higgs_avg_cognitive_mass', 'Average cognitive mass across nodes')
higgs_potential_energy = Gauge('qbc_higgs_potential_energy', 'Current Higgs potential energy V(phi)')

# ============================================================================
# FEE COLLECTOR METRICS
# ============================================================================
fees_collected_total = Gauge('qbc_fees_collected_total', 'Total fee collection events')
fees_collected_qbc_total = Gauge('qbc_fees_collected_qbc_total', 'Total QBC collected in fees')

# ============================================================================
# QUSD ORACLE METRICS
# ============================================================================
qusd_price_qbc_usd = Gauge('qbc_qusd_price_qbc_usd', 'QBC/USD price from QUSD oracle')
qusd_oracle_stale = Gauge('qbc_qusd_oracle_stale', 'QUSD oracle staleness flag (0/1)')

# ============================================================================
# QUSD KEEPER METRICS
# ============================================================================
qusd_keeper_mode = Gauge('qbc_qusd_keeper_mode', 'Keeper operating mode (0=off,1=scan,2=periodic,3=continuous,4=aggressive)')
qusd_keeper_last_check_block = Gauge('qbc_qusd_keeper_last_check_block', 'Last block checked by keeper')
qusd_keeper_actions_total = Counter('qbc_qusd_keeper_actions_total', 'Total keeper actions executed')
qusd_keeper_depeg_events_total = Counter('qbc_qusd_keeper_depeg_events_total', 'Total depeg events detected')
qusd_keeper_stability_fund = Gauge('qbc_qusd_keeper_stability_fund', 'Stability fund balance (QBC)')
qusd_keeper_max_deviation = Gauge('qbc_qusd_keeper_max_deviation', 'Max wQUSD price deviation from $1')
qusd_keeper_paused = Gauge('qbc_qusd_keeper_paused', 'Keeper paused flag (0/1)')
qusd_keeper_arb_opportunities = Gauge('qbc_qusd_keeper_arb_opportunities', 'Current profitable arb opportunities')

# ============================================================================
# CAPABILITY METRICS
# ============================================================================
capability_active_peers = Gauge('qbc_capability_active_peers', 'Active peers with known capabilities')
capability_total_mining_power = Gauge('qbc_capability_total_mining_power', 'Total network mining power estimate')

# ============================================================================
# IPFS MEMORY METRICS
# ============================================================================
ipfs_memory_stored_total = Counter('qbc_ipfs_memory_stored_total', 'Total IPFS memory store operations')
ipfs_memory_cache_size = Gauge('qbc_ipfs_memory_cache_size', 'IPFS memory cache size')

# ============================================================================
# SPV METRICS
# ============================================================================
spv_verifications_total = Counter('qbc_spv_verifications_total', 'Total SPV verifications')

# ============================================================================
# SUBSYSTEM HEALTH METRICS
# ============================================================================
subsystem_bridge_up = Gauge('qbc_subsystem_bridge_up', 'Bridge subsystem up (0/1)')
subsystem_stablecoin_up = Gauge('qbc_subsystem_stablecoin_up', 'Stablecoin subsystem up (0/1)')
subsystem_compliance_up = Gauge('qbc_subsystem_compliance_up', 'Compliance subsystem up (0/1)')
subsystem_plugins_up = Gauge('qbc_subsystem_plugins_up', 'Plugin subsystem up (0/1)')
subsystem_cognitive_up = Gauge('qbc_subsystem_cognitive_up', 'Cognitive architecture up (0/1)')
subsystem_privacy_up = Gauge('qbc_subsystem_privacy_up', 'Privacy subsystem up (0/1)')

# ============================================================================
# AIKGS (Aether Incentivized Knowledge Growth System) METRICS
# ============================================================================
aikgs_total_contributions = Gauge('qbc_aikgs_total_contributions', 'Total AIKGS knowledge contributions')
aikgs_total_rewards_distributed = Gauge('qbc_aikgs_total_rewards_distributed', 'Total QBC rewards distributed via AIKGS')
aikgs_pool_balance = Gauge('qbc_aikgs_pool_balance', 'AIKGS reward pool balance in QBC')
aikgs_unique_contributors = Gauge('qbc_aikgs_unique_contributors', 'Unique contributors in AIKGS')
aikgs_tier_bronze = Gauge('qbc_aikgs_tier_bronze', 'Bronze tier contributions')
aikgs_tier_silver = Gauge('qbc_aikgs_tier_silver', 'Silver tier contributions')
aikgs_tier_gold = Gauge('qbc_aikgs_tier_gold', 'Gold tier contributions')
aikgs_tier_diamond = Gauge('qbc_aikgs_tier_diamond', 'Diamond tier contributions')
aikgs_affiliates_total = Gauge('qbc_aikgs_affiliates_total', 'Total registered affiliates')
aikgs_commissions_total = Gauge('qbc_aikgs_commissions_total', 'Total affiliate commissions in QBC')
aikgs_bounties_active = Gauge('qbc_aikgs_bounties_active', 'Active knowledge bounties')
aikgs_curation_pending = Gauge('qbc_aikgs_curation_pending', 'Pending curation rounds')
aikgs_api_keys_active = Gauge('qbc_aikgs_api_keys_active', 'Active API keys in vault')
aikgs_shared_keys_pool = Gauge('qbc_aikgs_shared_keys_pool', 'Keys in shared pool')

# ============================================================================
# REVERSIBILITY METRICS
# ============================================================================
reversal_requests_total = Gauge('qbc_reversal_requests_total', 'Total reversal requests')
reversal_executed_total = Gauge('qbc_reversal_executed_total', 'Total executed reversals')
active_guardians = Gauge('qbc_active_guardians', 'Active security guardians')
reversible_transactions = Gauge('qbc_reversible_transactions', 'Transactions with active reversal windows')
dilithium_security_level = Gauge('qbc_dilithium_security_level', 'Current Dilithium security level (2/3/5)')

# ============================================================================
# INHERITANCE PROTOCOL METRICS
# ============================================================================
inheritance_active_plans = Gauge('qbc_inheritance_active_plans', 'Active inheritance plans')
inheritance_pending_claims = Gauge('qbc_inheritance_pending_claims', 'Pending inheritance claims')
inheritance_executed_claims = Counter('qbc_inheritance_executed_claims_total', 'Total executed inheritance claims')
inheritance_cancelled_claims = Counter('qbc_inheritance_cancelled_claims_total', 'Total cancelled inheritance claims')

# ============================================================================
# HIGH-SECURITY ACCOUNT METRICS
# ============================================================================
security_active_policies = Gauge('qbc_security_active_policies', 'Active high-security policies')
security_blocked_txs = Counter('qbc_security_blocked_txs_total', 'Transactions blocked by security policies')
security_time_locked_txs = Counter('qbc_security_time_locked_txs_total', 'Transactions time-locked by security policies')

# ============================================================================
# STRATUM MINING METRICS
# ============================================================================
stratum_workers_connected = Gauge('qbc_stratum_workers_connected', 'Connected stratum workers')
stratum_shares_submitted = Counter('qbc_stratum_shares_submitted_total', 'Total shares submitted')
stratum_shares_accepted = Counter('qbc_stratum_shares_accepted_total', 'Total shares accepted')
stratum_shares_rejected = Counter('qbc_stratum_shares_rejected_total', 'Total shares rejected')
stratum_blocks_found = Counter('qbc_stratum_blocks_found_total', 'Total blocks found via stratum')

# ============================================================================
# DENIABLE RPC METRICS
# ============================================================================
deniable_batch_queries = Counter('qbc_deniable_batch_queries_total', 'Total deniable batch queries')
deniable_bloom_queries = Counter('qbc_deniable_bloom_queries_total', 'Total deniable bloom queries')
deniable_avg_batch_size = Gauge('qbc_deniable_avg_batch_size', 'Average deniable batch size')

# ============================================================================
# FINALITY METRICS
# ============================================================================
finality_last_finalized = Gauge('qbc_finality_last_finalized_height', 'Last finalized block height')
finality_validator_count = Gauge('qbc_finality_validator_count', 'Number of registered finality validators')
finality_total_stake = Gauge('qbc_finality_total_stake', 'Total stake of finality validators')
finality_votes_cast = Counter('qbc_finality_votes_cast_total', 'Total finality votes cast')
finality_checkpoints = Counter('qbc_finality_checkpoints_total', 'Total finality checkpoints recorded')
finality_vote_ratio = Gauge('qbc_finality_vote_ratio', 'Current vote ratio for latest block')
finality_reorgs_blocked = Counter('qbc_finality_reorgs_blocked_total', 'Reorgs blocked by finality')
finality_enabled = Gauge('qbc_finality_enabled', 'Whether finality gadget is enabled')

# ============================================================================
# INVESTOR PUBLIC SALE METRICS
# ============================================================================
investor_total_raised = Gauge('qbc_investor_total_raised_usd', 'Total USD raised in seed round')
investor_count = Gauge('qbc_investor_count', 'Total investors in seed round')
investor_vesting_claimed = Counter('qbc_investor_vesting_claimed_total', 'Total QBC claimed via vesting')
investor_revenue_distributed = Counter('qbc_investor_revenue_distributed_total', 'Total QBC distributed as revenue')
investor_revenue_pending = Gauge('qbc_investor_revenue_pending', 'Unclaimed investor revenue QBC')
investor_round_active = Gauge('qbc_investor_round_active', 'Whether a round is currently active')

def setup_metrics(app) -> None:
    """Setup Prometheus metrics for FastAPI app"""
    instrumentator = Instrumentator().instrument(app).expose(app)
    return instrumentator

# Export functions
__all__ = [
    # Blockchain
    'blocks_mined', 'blocks_received', 'current_height_metric',
    'total_supply_metric', 'current_difficulty_metric', 'avg_block_time_metric',
    'total_fees_burned_metric',
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
    # Bridge
    'bridge_active_chains', 'bridge_deposits_total', 'bridge_withdrawals_total', 'bridge_tvl',
    # Privacy
    'privacy_commitments_created', 'privacy_range_proofs_generated', 'privacy_stealth_outputs_created',
    # Compliance
    'compliance_policies_total', 'compliance_blocked_addresses', 'compliance_circuit_breaker',
    'aml_alerts_total', 'sanctions_entries_total',
    # Plugins
    'qvm_plugins_registered', 'qvm_plugins_active',
    # QVM Extensions
    'qvm_state_channels_open', 'qvm_state_channels_tvl', 'qvm_batch_pending_txs',
    'qvm_decoherence_active', 'qvm_token_transfers_total', 'tlac_pending',
    # Stablecoin
    'qusd_total_supply', 'qusd_reserve_backing_pct', 'qusd_active_vaults', 'qusd_total_debt',
    # Cognitive Architecture
    'sephirot_active_nodes', 'sephirot_susy_violations_total', 'sephirot_susy_corrections_total',
    'csf_messages_delivered_total', 'csf_queue_depth',
    'pineal_current_phase', 'pineal_metabolic_rate', 'pineal_is_conscious',
    'safety_vetoes_total', 'safety_evaluations_total',
    # Higgs Cognitive Field
    'higgs_field_value', 'higgs_vev', 'higgs_deviation_pct',
    'higgs_mass_gap', 'higgs_excitations_total',
    'higgs_avg_cognitive_mass', 'higgs_potential_energy',
    # Fee Collector
    'fees_collected_total', 'fees_collected_qbc_total',
    # QUSD Oracle
    'qusd_price_qbc_usd', 'qusd_oracle_stale',
    # QUSD Keeper
    'qusd_keeper_mode', 'qusd_keeper_last_check_block',
    'qusd_keeper_actions_total', 'qusd_keeper_depeg_events_total',
    'qusd_keeper_stability_fund', 'qusd_keeper_max_deviation',
    'qusd_keeper_paused', 'qusd_keeper_arb_opportunities',
    # Capability
    'capability_active_peers', 'capability_total_mining_power',
    # IPFS Memory
    'ipfs_memory_stored_total', 'ipfs_memory_cache_size',
    # SPV
    'spv_verifications_total',
    # Subsystem Health
    'subsystem_bridge_up', 'subsystem_stablecoin_up', 'subsystem_compliance_up',
    'subsystem_plugins_up', 'subsystem_cognitive_up', 'subsystem_privacy_up',
    # AIKGS
    'aikgs_total_contributions', 'aikgs_total_rewards_distributed', 'aikgs_pool_balance',
    'aikgs_unique_contributors', 'aikgs_tier_bronze', 'aikgs_tier_silver',
    'aikgs_tier_gold', 'aikgs_tier_diamond', 'aikgs_affiliates_total',
    'aikgs_commissions_total', 'aikgs_bounties_active', 'aikgs_curation_pending',
    'aikgs_api_keys_active', 'aikgs_shared_keys_pool',
    # Reversibility
    'reversal_requests_total', 'reversal_executed_total', 'active_guardians',
    'reversible_transactions', 'dilithium_security_level',
    # Inheritance
    'inheritance_active_plans', 'inheritance_pending_claims',
    'inheritance_executed_claims', 'inheritance_cancelled_claims',
    # High-Security
    'security_active_policies', 'security_blocked_txs', 'security_time_locked_txs',
    # Stratum
    'stratum_workers_connected', 'stratum_shares_submitted',
    'stratum_shares_accepted', 'stratum_shares_rejected', 'stratum_blocks_found',
    # Deniable RPC
    'deniable_batch_queries', 'deniable_bloom_queries', 'deniable_avg_batch_size',
    # Finality
    'finality_last_finalized', 'finality_validator_count', 'finality_total_stake',
    'finality_votes_cast', 'finality_checkpoints', 'finality_vote_ratio',
    'finality_reorgs_blocked', 'finality_enabled',
    # Investor
    'investor_total_raised', 'investor_count', 'investor_vesting_claimed',
    'investor_revenue_distributed', 'investor_revenue_pending', 'investor_round_active',
    # Setup
    'setup_metrics', 'generate_latest', 'CONTENT_TYPE_LATEST',
]
