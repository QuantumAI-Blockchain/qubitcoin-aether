"""
Qubitcoin Full Node - Main Entry Point
Coordinates all components and manages node lifecycle
"""
import asyncio
import os
import signal
import subprocess
import sys
import time
from decimal import getcontext
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from .config import Config
from .database.manager import DatabaseManager
from .quantum.engine import QuantumEngine
from .consensus.engine import ConsensusEngine
from .mining.engine import MiningEngine
from .storage.ipfs import IPFSManager
from .network.rpc import create_rpc_app
from .network.p2p_network import P2PNetwork
from .network.rust_p2p_client import RustP2PClient
from .contracts.executor import ContractExecutor
from .qvm.state import StateManager
from .aether import KnowledgeGraph, PhiCalculator, ReasoningEngine, AetherEngine
from .aether.genesis import AetherGenesis
from .utils.logger import get_logger

# Import metrics (only those that are instrumented)
from .utils.metrics import (
    # Blockchain
    blocks_mined, blocks_received, current_height_metric, total_supply_metric,
    current_difficulty_metric, avg_block_time_metric,
    # Mining
    alignment_score_metric,
    # Network
    active_peers, rust_p2p_peers,
    # Transactions
    transactions_pending, transactions_confirmed,
    # Quantum Research
    quantum_backend_metric, active_hamiltonians, vqe_solutions_total,
    # QVM
    total_contracts, active_contracts,
    # AGI
    phi_current, phi_threshold_distance, knowledge_nodes_total, knowledge_edges_total,
    reasoning_operations_total, consciousness_events_total, integration_score,
    differentiation_score,
    # IPFS
    blockchain_snapshots_total,
    # Bridge
    bridge_active_chains,
    # Compliance
    compliance_policies_total, compliance_blocked_addresses, compliance_circuit_breaker,
    sanctions_entries_total,
    # Plugins
    qvm_plugins_registered, qvm_plugins_active,
    # QVM Extensions
    qvm_state_channels_open, qvm_state_channels_tvl, qvm_batch_pending_txs,
    qvm_decoherence_active, tlac_pending,
    # Stablecoin
    qusd_total_supply, qusd_reserve_backing_pct, qusd_active_vaults, qusd_total_debt,
    # Cognitive Architecture
    sephirot_active_nodes, csf_queue_depth,
    pineal_current_phase, pineal_metabolic_rate, pineal_is_conscious,
    # Higgs Cognitive Field
    higgs_field_value, higgs_vev, higgs_deviation_pct,
    higgs_mass_gap, higgs_excitations_total,
    higgs_avg_cognitive_mass, higgs_potential_energy,
    # Fee Collector
    fees_collected_total, fees_collected_qbc_total,
    # QUSD Oracle
    qusd_price_qbc_usd, qusd_oracle_stale,
    # Capability
    capability_active_peers, capability_total_mining_power,
    # IPFS Memory
    ipfs_memory_cache_size,
    # Subsystem Health
    subsystem_bridge_up, subsystem_stablecoin_up, subsystem_compliance_up,
    subsystem_plugins_up, subsystem_cognitive_up, subsystem_privacy_up,
    # AIKGS
    aikgs_total_contributions, aikgs_total_rewards_distributed, aikgs_pool_balance,
    aikgs_unique_contributors, aikgs_tier_bronze, aikgs_tier_silver,
    aikgs_tier_gold, aikgs_tier_diamond, aikgs_affiliates_total,
    aikgs_commissions_total, aikgs_bounties_active, aikgs_curation_pending,
    aikgs_api_keys_active, aikgs_shared_keys_pool,
)

getcontext().prec = 28
logger = get_logger(__name__)
console = Console()

class QubitcoinNode:
    """Main node orchestrator with P2P networking, QVM, and Aether Tree"""

    def __init__(self):
        """Initialize all node components"""
        self.console = console
        self.running = False
        self.metrics_task = None
        self.rust_p2p_process: subprocess.Popen | None = None

        logger.info("=" * 60)
        logger.info("Qubitcoin Full Node Initializing")
        logger.info("=" * 60)

        console.print(Config.display())

        logger.info("Initializing components...")

        # Component 1: Database
        logger.info("[1/22] Initializing DatabaseManager...")
        try:
            self.db = DatabaseManager()
            logger.info("[1/22] DatabaseManager initialized")
        except Exception as e:
            logger.error(f"[1/22] DatabaseManager failed: {e}", exc_info=True)
            raise

        # Component 2: Quantum Engine
        logger.info("[2/22] Initializing QuantumEngine...")
        try:
            self.quantum = QuantumEngine()
            logger.info("[2/22] QuantumEngine initialized")
        except Exception as e:
            logger.error(f"[2/22] QuantumEngine failed: {e}", exc_info=True)
            raise

        # Component 3: P2P Network (Python or Rust)
        logger.info("[3/22] Initializing P2P Network...")
        try:
            if Config.ENABLE_RUST_P2P:
                logger.info("Using Rust P2P (libp2p 0.56)")
                # Launch the Rust daemon process
                self._start_rust_p2p_daemon()
                self.rust_p2p = RustP2PClient(f"127.0.0.1:{Config.RUST_P2P_GRPC}")
                self.p2p = None  # Disable Python P2P
                logger.info("[3/22] Rust P2P client initialized")
            else:
                logger.info("Using Python P2P (legacy)")
                self.p2p = P2PNetwork(
                    port=Config.P2P_PORT,
                    peer_id=Config.ADDRESS[:16],
                    consensus=None,
                    max_peers=Config.MAX_PEERS
                )
                self.rust_p2p = None
                logger.info("[3/22] Python P2P initialized")
        except Exception as e:
            logger.error(f"[3/22] P2P initialization failed: {e}", exc_info=True)
            raise

        # Component 4: Consensus Engine
        logger.info("[4/22] Initializing ConsensusEngine...")
        try:
            self.consensus = ConsensusEngine(self.quantum, self.db, self.p2p)
            if self.p2p:
                self.p2p.consensus = self.consensus
            logger.info("[4/22] ConsensusEngine initialized")
        except Exception as e:
            logger.error(f"[4/22] ConsensusEngine failed: {e}", exc_info=True)
            raise

        # Component 5: IPFS
        logger.info("[5/22] Initializing IPFSManager...")
        try:
            self.ipfs = IPFSManager()
            logger.info("[5/22] IPFSManager initialized")
        except Exception as e:
            logger.error(f"[5/22] IPFSManager failed: {e}", exc_info=True)
            raise

        # Component 6: QVM State Manager (bytecode VM + state roots)
        logger.info("[6/22] Initializing QVM StateManager...")
        try:
            self.state_manager = StateManager(self.db, self.quantum)
            self.consensus.state_manager = self.state_manager

            # Wire EventIndex into StateManager for in-memory event log indexing
            from .qvm.event_index import EventIndex
            self.event_index = EventIndex(db_manager=self.db)
            self.state_manager.event_index = self.event_index
            logger.info("[6/22] QVM StateManager initialized (155 opcodes, 10 quantum, EventIndex)")
        except Exception as e:
            logger.error(f"[6/22] QVM StateManager failed: {e}", exc_info=True)
            raise

        # Component 7: Aether Tree (AGI layer)
        logger.info("[7/22] Initializing Aether Engine...")
        try:
            self.knowledge_graph = KnowledgeGraph(self.db)
            self.phi_calculator = PhiCalculator(self.db, self.knowledge_graph)
            self.reasoning_engine = ReasoningEngine(self.db, self.knowledge_graph)
            self.aether = AetherEngine(
                self.db, self.knowledge_graph,
                self.phi_calculator, self.reasoning_engine
            )
            self.consensus.aether = self.aether

            # Instantiate Proof-of-Thought protocol and wire to Aether
            from .aether.task_protocol import ProofOfThoughtProtocol
            self.pot_protocol = ProofOfThoughtProtocol()
            self.aether.pot_protocol = self.pot_protocol
            logger.info("Proof-of-Thought protocol wired to Aether Engine")

            # Initialize AGI from genesis if this is the first run
            self.aether_genesis = AetherGenesis(
                self.db, self.knowledge_graph, self.phi_calculator
            )
            if not self.aether_genesis.is_genesis_initialized():
                try:
                    genesis_block = self.db.get_block(0)
                    genesis_hash = genesis_block.block_hash if genesis_block else '0' * 64
                    genesis_ts = genesis_block.timestamp if genesis_block else None
                    result = self.aether_genesis.initialize_genesis(genesis_hash, genesis_ts)
                    logger.info(
                        f"Aether genesis initialized: "
                        f"{result['knowledge_nodes_created']} nodes seeded"
                    )
                except Exception as e:
                    logger.debug(f"Aether genesis init skipped (DB not ready): {e}")

            # Phase 6: On-chain AGI integration
            try:
                from .aether.on_chain import OnChainAGI
                self.on_chain = OnChainAGI(self.state_manager)
                self.aether.on_chain = self.on_chain
                logger.info("OnChainAGI bridge wired to Aether Engine")
            except Exception as e:
                self.on_chain = None
                logger.debug(f"OnChainAGI init skipped: {e}")

            logger.info("[7/22] Aether Engine initialized (KnowledgeGraph + Phi + Reasoning + PoT)")
        except Exception as e:
            logger.error(f"[7/22] Aether Engine failed: {e}", exc_info=True)
            raise

        # Component 7c: AIKGS — now runs as a Rust sidecar (gRPC client).
        # The 8 Python AIKGS modules have been replaced by a single gRPC client.
        self.aikgs_client = None
        self.aikgs_telegram_bot = None  # Telegram bot still runs in Python

        # Component 7b: LLM Adapters + Knowledge Seeder (optional)
        self.llm_manager = None
        self.knowledge_seeder = None
        if Config.LLM_ENABLED:
            try:
                from .aether.llm_adapter import (
                    LLMAdapterManager, OpenAIAdapter, ClaudeAdapter, LocalAdapter,
                )
                self.llm_manager = LLMAdapterManager(self.knowledge_graph)

                # Register adapters in priority order based on LLM_PRIMARY_ADAPTER
                primary = Config.LLM_PRIMARY_ADAPTER
                adapters_to_register = []
                if Config.OPENAI_API_KEY:
                    adapters_to_register.append((
                        OpenAIAdapter(
                            api_key=Config.OPENAI_API_KEY,
                            model=Config.OPENAI_MODEL,
                            max_tokens=Config.OPENAI_MAX_TOKENS,
                            temperature=Config.OPENAI_TEMPERATURE,
                        ),
                        10 if primary == 'openai' else 50,
                    ))
                if Config.CLAUDE_API_KEY:
                    adapters_to_register.append((
                        ClaudeAdapter(
                            api_key=Config.CLAUDE_API_KEY,
                            model=Config.CLAUDE_MODEL,
                        ),
                        10 if primary == 'claude' else 50,
                    ))
                if Config.LOCAL_LLM_URL:
                    adapters_to_register.append((
                        LocalAdapter(base_url=Config.LOCAL_LLM_URL),
                        10 if primary == 'local' else 90,
                    ))

                for adapter, priority in adapters_to_register:
                    self.llm_manager.register_adapter(adapter, priority)

                available = self.llm_manager.get_available_adapters()
                logger.info(f"LLM adapters initialized: {available}")

                # Knowledge Seeder
                if Config.LLM_SEEDER_ENABLED and available:
                    from .aether.knowledge_seeder import KnowledgeSeeder
                    self.knowledge_seeder = KnowledgeSeeder(self.llm_manager, self.db)
                    logger.info("Knowledge seeder initialized (will start on node startup)")
            except Exception as e:
                logger.warning(f"LLM initialization failed (non-fatal): {e}")
                self.llm_manager = None
                self.knowledge_seeder = None

        # ================================================================
        # NEW SUBSYSTEM WIRING (Components 8-20) — all non-fatal
        # ================================================================

        # Component 8: Fee Collector
        self.fee_collector = None
        try:
            from .utils.fee_collector import FeeCollector
            self.fee_collector = FeeCollector(self.db)
            logger.info("[8/22] FeeCollector initialized")
        except Exception as e:
            logger.warning(f"[8/22] FeeCollector failed (non-fatal): {e}")

        # Component 9: QUSD Oracle
        self.qusd_oracle = None
        try:
            from .utils.qusd_oracle import QUSDOracle
            self.qusd_oracle = QUSDOracle(self.state_manager)
            logger.info("[9/22] QUSDOracle initialized")
        except Exception as e:
            logger.warning(f"[9/22] QUSDOracle failed (non-fatal): {e}")

        # Component 10: Compliance Engine + AML Monitor
        self.compliance_engine = None
        self.aml_monitor = None
        try:
            from .qvm.compliance import ComplianceEngine
            self.compliance_engine = ComplianceEngine(self.db)
            # Wire compliance engine into QVM for QCOMPLIANCE opcode
            if self.state_manager:
                self.state_manager.qvm.compliance = self.compliance_engine
            logger.info("[10/22] ComplianceEngine initialized (wired to QVM QCOMPLIANCE)")
        except Exception as e:
            logger.warning(f"[10/22] ComplianceEngine failed (non-fatal): {e}")
        try:
            from .qvm.aml import AMLMonitor
            self.aml_monitor = AMLMonitor()
            logger.info("[10/22] AMLMonitor initialized")
        except Exception as e:
            logger.warning(f"[10/22] AMLMonitor failed (non-fatal): {e}")

        # Component 11: Compliance Proof Store + TLAC + Risk Normalizer
        self.compliance_proof_store = None
        self.tlac_manager = None
        self.risk_normalizer = None
        try:
            from .qvm.compliance_proofs import ComplianceProofStore
            self.compliance_proof_store = ComplianceProofStore()
            logger.info("[11/22] ComplianceProofStore initialized")
        except Exception as e:
            logger.warning(f"[11/22] ComplianceProofStore failed (non-fatal): {e}")
        try:
            from .qvm.compliance_advanced import TLACManager
            self.tlac_manager = TLACManager()
            logger.info("[11/22] TLACManager initialized")
        except Exception as e:
            logger.warning(f"[11/22] TLACManager failed (non-fatal): {e}")
        try:
            from .qvm.risk import RiskNormalizer
            self.risk_normalizer = RiskNormalizer()
            logger.info("[11/22] RiskNormalizer initialized")
        except Exception as e:
            logger.warning(f"[11/22] RiskNormalizer failed (non-fatal): {e}")

        # Component 12: Plugin Manager + register plugins
        self.plugin_manager = None
        try:
            from .qvm.plugins import PluginManager
            self.plugin_manager = PluginManager()
            # Register available plugins
            self._register_plugins()
            logger.info("[12/22] PluginManager initialized")
        except Exception as e:
            logger.warning(f"[12/22] PluginManager failed (non-fatal): {e}")

        # Component 13: QVM Extensions (standalone modules)
        self.decoherence_manager = None
        self.transaction_batcher = None
        self.state_channel_manager = None
        self.qvm_debugger = None
        self.qsol_compiler = None
        self.systemic_risk_model = None
        self.tx_graph = None
        try:
            from .qvm.decoherence import DecoherenceManager
            self.decoherence_manager = DecoherenceManager()
        except Exception as e:
            logger.debug(f"DecoherenceManager init: {e}")
        try:
            from .qvm.transaction_batcher import TransactionBatcher
            self.transaction_batcher = TransactionBatcher()
        except Exception as e:
            logger.debug(f"TransactionBatcher init: {e}")
        try:
            from .qvm.state_channels import StateChannelManager
            self.state_channel_manager = StateChannelManager()
        except Exception as e:
            logger.debug(f"StateChannelManager init: {e}")
        try:
            from .qvm.debugger import QVMDebugger
            self.qvm_debugger = QVMDebugger()
        except Exception as e:
            logger.debug(f"QVMDebugger init: {e}")
        try:
            from .qvm.qsol_compiler import QSolCompiler
            self.qsol_compiler = QSolCompiler()
        except Exception as e:
            logger.debug(f"QSolCompiler init: {e}")
        try:
            from .qvm.systemic_risk import SystemicRiskModel
            self.systemic_risk_model = SystemicRiskModel()
        except Exception as e:
            logger.debug(f"SystemicRiskModel init: {e}")
        try:
            from .qvm.tx_graph import TransactionGraph
            self.tx_graph = TransactionGraph()
        except Exception as e:
            logger.debug(f"TransactionGraph init: {e}")
        logger.info("[13/22] QVM extensions initialized")

        # Component 14: Stablecoin Engine
        self.stablecoin_engine = None
        self.reserve_fee_router = None
        self.reserve_verifier = None
        try:
            from .stablecoin.engine import StablecoinEngine
            self.stablecoin_engine = StablecoinEngine(self.db, self.quantum)
            logger.info("[14/22] StablecoinEngine initialized")
        except Exception as e:
            logger.warning(f"[14/22] StablecoinEngine failed (non-fatal): {e}")
        try:
            from .stablecoin.reserve_manager import ReserveFeeRouter
            self.reserve_fee_router = ReserveFeeRouter()
        except Exception as e:
            logger.debug(f"ReserveFeeRouter init: {e}")
        try:
            from .stablecoin.reserve_verification import ReserveVerifier
            self.reserve_verifier = ReserveVerifier()
        except Exception as e:
            logger.debug(f"ReserveVerifier init: {e}")

        # Component 15: Bridge Manager + Liquidity Pool
        self.bridge_manager = None
        self.bridge_lp = None
        try:
            from .bridge.manager import BridgeManager
            self.bridge_manager = BridgeManager(self.db)
            logger.info("[15/22] BridgeManager initialized")
        except Exception as e:
            logger.warning(f"[15/22] BridgeManager failed (non-fatal): {e}")
        try:
            from .bridge.liquidity_pool import BridgeLiquidityPool
            self.bridge_lp = BridgeLiquidityPool()
            logger.info("[15/22] BridgeLiquidityPool initialized")
        except Exception as e:
            logger.debug(f"BridgeLiquidityPool init: {e}")

        # Component 16: Cognitive Architecture
        self.sephirot_manager = None
        self.csf_transport = None
        self.pineal_orchestrator = None
        self.safety_manager = None
        try:
            from .aether.sephirot import SephirotManager
            self.sephirot_manager = SephirotManager(self.db, self.state_manager)
            logger.info("[16/22] SephirotManager initialized")
        except Exception as e:
            logger.warning(f"[16/22] SephirotManager failed (non-fatal): {e}")
        try:
            from .aether.csf_transport import CSFTransport
            self.csf_transport = CSFTransport()
            logger.info("[16/22] CSFTransport initialized")
        except Exception as e:
            logger.debug(f"CSFTransport init: {e}")
        try:
            from .aether.pineal import PinealOrchestrator
            if self.sephirot_manager:
                self.pineal_orchestrator = PinealOrchestrator(self.sephirot_manager)
                logger.info("[16/22] PinealOrchestrator initialized")
            else:
                logger.debug("PinealOrchestrator skipped — SephirotManager not available")
        except Exception as e:
            logger.debug(f"PinealOrchestrator init: {e}")
        try:
            from .aether.safety import SafetyManager
            self.safety_manager = SafetyManager()
            logger.info("[16/22] SafetyManager initialized")
        except Exception as e:
            logger.debug(f"SafetyManager init: {e}")

        # Component 16b: Neural Reasoner (GATReasoner)
        self.neural_reasoner = None
        try:
            from .aether.neural_reasoner import GATReasoner
            self.neural_reasoner = GATReasoner(hidden_dim=64, n_heads=4)
            logger.info("[16/22] GATReasoner (neural reasoner) initialized")
        except Exception as e:
            logger.debug(f"GATReasoner init: {e}")

        # Component 16c: Higgs Cognitive Field
        self.higgs_field = None
        self.higgs_susy = None
        try:
            if Config.HIGGS_ENABLE_MASS_REBALANCING and self.sephirot_manager:
                from .aether.higgs_field import HiggsCognitiveField, HiggsSUSYSwap
                self.higgs_field = HiggsCognitiveField(self.sephirot_manager)
                self.higgs_field.initialize()
                self.higgs_susy = HiggsSUSYSwap(self.higgs_field, self.sephirot_manager)
                logger.info("[16c/22] Higgs Cognitive Field initialized (mass rebalancing enabled)")
            else:
                logger.debug("[16c/22] Higgs Cognitive Field skipped (disabled or no SephirotManager)")
        except Exception as e:
            logger.warning(f"[16c/22] Higgs Cognitive Field init failed (non-fatal): {e}")
            self.higgs_field = None
            self.higgs_susy = None

        # Wire cognitive + LLM components into AetherEngine
        if hasattr(self, 'aether') and self.aether:
            if self.pineal_orchestrator:
                self.aether.pineal = self.pineal_orchestrator
            if self.csf_transport:
                self.aether.csf = self.csf_transport
            if self.llm_manager:
                self.aether.llm_manager = self.llm_manager
            if self.neural_reasoner:
                self.aether.neural_reasoner = self.neural_reasoner
            if self.sephirot_manager:
                self.aether.set_sephirot_manager(self.sephirot_manager)
            logger.info("[16/22] Cognitive + LLM + Neural components wired to Aether Engine")

        # Component 17: SPV Verifier
        self.spv_verifier = None
        try:
            from .network.light_node import SPVVerifier
            self.spv_verifier = SPVVerifier()
            logger.info("[17/22] SPVVerifier initialized")
        except Exception as e:
            logger.debug(f"SPVVerifier init: {e}")

        # Component 18: IPFS Memory Store
        self.ipfs_memory = None
        try:
            from .aether.ipfs_memory import IPFSMemoryStore
            self.ipfs_memory = IPFSMemoryStore(self.ipfs)
            logger.info("[18/22] IPFSMemoryStore initialized")
        except Exception as e:
            logger.debug(f"IPFSMemoryStore init: {e}")

        # Component 19: Capability Advertiser
        self.capability_advertiser = None
        try:
            from .network.capability_advertisement import CapabilityAdvertiser
            peer_id = Config.ADDRESS[:16]
            self.capability_advertiser = CapabilityAdvertiser(node_peer_id=peer_id)
            logger.info("[19/22] CapabilityAdvertiser initialized")
        except Exception as e:
            logger.debug(f"CapabilityAdvertiser init: {e}")

        # Component 19b: Exchange Engine (DEX order book)
        self.exchange_engine = None
        try:
            from .exchange.engine import ExchangeEngine
            self.exchange_engine = ExchangeEngine()
            logger.info("[19b/22] ExchangeEngine initialized (%d pairs)",
                        len(self.exchange_engine.books))
        except Exception as e:
            logger.warning(f"[19b/22] ExchangeEngine failed (non-fatal): {e}")

        # Component 20: Mining Engine
        logger.info("[20/22] Initializing MiningEngine...")
        try:
            self.mining = MiningEngine(self.quantum, self.consensus, self.db, console,
                                       state_manager=self.state_manager,
                                       aether_engine=self.aether)
            self.mining.node = self
            logger.info("[20/22] MiningEngine initialized")
        except Exception as e:
            logger.error(f"[20/22] MiningEngine failed: {e}", exc_info=True)
            raise

        # Component 20b: AIKGS — Rust sidecar client (replaces 8 Python modules)
        if Config.AIKGS_ENABLED and Config.AIKGS_USE_RUST_SIDECAR:
            try:
                from .aether.aikgs_client import AikgsClient
                grpc_addr = f"{Config.AIKGS_GRPC_ADDR}:{Config.AIKGS_GRPC_PORT}"
                self.aikgs_client = AikgsClient(grpc_addr, auth_token=Config.AIKGS_AUTH_TOKEN)
                # Connection happens async in on_startup
                logger.info(f"[20b/22] AIKGS sidecar client created (will connect to {grpc_addr})")
            except Exception as e:
                logger.warning(f"[20b/22] AIKGS sidecar client init failed (non-critical): {e}", exc_info=True)
        elif Config.AIKGS_ENABLED:
            logger.warning("[20b/22] AIKGS_USE_RUST_SIDECAR=false — AIKGS disabled (Python modules removed)")

        # Telegram bot (still Python — bridges to sidecar via aikgs_client)
        if Config.AIKGS_ENABLED and Config.TELEGRAM_BOT_TOKEN:
            try:
                from .aether.telegram_bot import TelegramBot
                self.aikgs_telegram_bot = TelegramBot(
                    contribution_manager=None,  # Not used — bot will use aikgs_client
                    affiliate_manager=None,
                    reward_engine=None,
                    progressive_unlocks=None,
                )
                logger.info("[20b/22] Telegram bot initialized")
            except Exception as e:
                logger.debug(f"[20b/22] Telegram bot init skipped: {e}")

        # Component 21: Contract Executor (legacy template contracts)
        logger.info("[21/22] Initializing ContractExecutor...")
        try:
            self.contracts = ContractExecutor(self.db, self.quantum)
            logger.info("[21/22] ContractExecutor initialized")
        except Exception as e:
            logger.error(f"[21/22] ContractExecutor failed: {e}", exc_info=True)
            raise

        # Component 22: RPC & Handlers
        logger.info("[22/22] Initializing RPC and handlers...")
        try:
            if self.p2p:
                self._setup_p2p_handlers()

            self.app = create_rpc_app(
                self.db,
                self.consensus,
                self.mining,
                self.quantum,
                self.ipfs,
                contract_engine=self.contracts,
                state_manager=self.state_manager,
                aether_engine=self.aether,
                llm_manager=self.llm_manager,
                pot_protocol=self.pot_protocol,
                # New subsystems
                fee_collector=self.fee_collector,
                qusd_oracle=self.qusd_oracle,
                compliance_engine=self.compliance_engine,
                aml_monitor=self.aml_monitor,
                compliance_proof_store=self.compliance_proof_store,
                tlac_manager=self.tlac_manager,
                risk_normalizer=self.risk_normalizer,
                plugin_manager=self.plugin_manager,
                decoherence_manager=self.decoherence_manager,
                transaction_batcher=self.transaction_batcher,
                state_channel_manager=self.state_channel_manager,
                qvm_debugger=self.qvm_debugger,
                qsol_compiler=self.qsol_compiler,
                systemic_risk_model=self.systemic_risk_model,
                tx_graph=self.tx_graph,
                stablecoin_engine=self.stablecoin_engine,
                reserve_fee_router=self.reserve_fee_router,
                reserve_verifier=self.reserve_verifier,
                bridge_manager=self.bridge_manager,
                sephirot_manager=self.sephirot_manager,
                csf_transport=self.csf_transport,
                pineal_orchestrator=self.pineal_orchestrator,
                safety_manager=self.safety_manager,
                spv_verifier=self.spv_verifier,
                ipfs_memory=self.ipfs_memory,
                capability_advertiser=self.capability_advertiser,
                on_chain_agi=getattr(self, 'on_chain', None),
                event_index=getattr(self, 'event_index', None),
                bridge_lp=self.bridge_lp,
                neural_reasoner=self.neural_reasoner,
                exchange_engine=self.exchange_engine,
                higgs_field=self.higgs_field,
                # AIKGS (Rust sidecar gRPC client)
                aikgs_client=self.aikgs_client,
                aikgs_telegram_bot=self.aikgs_telegram_bot,
            )
            self.app.node = self
            self.app.on_event("startup")(self.on_startup)
            self.app.on_event("shutdown")(self.on_shutdown)

            # Wire RPC-created trackers back into engines so they receive data
            if self.aether and hasattr(self.app, 'consciousness_dashboard'):
                self.aether.consciousness_dashboard = self.app.consciousness_dashboard
            if hasattr(self.app, 'circulation_tracker'):
                self.mining.circulation_tracker = self.app.circulation_tracker

            logger.info("[22/22] RPC and handlers initialized")
        except Exception as e:
            logger.error(f"[22/22] RPC initialization failed: {e}", exc_info=True)
            raise

        logger.info("All 22 components initialized successfully")

    def _register_plugins(self) -> None:
        """Register QVM plugins (DeFi, Governance, Oracle, Privacy)."""
        if not self.plugin_manager:
            return
        plugin_list = [
            ('defi', '.qvm.defi_plugin', 'DeFiPlugin'),
            ('governance', '.qvm.governance_plugin', 'GovernancePlugin'),
            ('oracle', '.qvm.oracle_plugin', 'OraclePlugin'),
            ('privacy', '.qvm.privacy_plugin', 'PrivacyPlugin'),
        ]
        for name, module_path, class_name in plugin_list:
            try:
                import importlib
                mod = importlib.import_module(module_path, package='qubitcoin')
                cls = getattr(mod, class_name)
                plugin = cls()
                self.plugin_manager.register(plugin)
                logger.debug(f"Plugin '{name}' registered")
            except Exception as e:
                logger.debug(f"Plugin '{name}' registration failed: {e}")

    def _setup_p2p_handlers(self):
        """Register handlers for Python P2P messages"""
        if not self.p2p:
            return

        self.p2p.register_handler('block', self._handle_received_block)
        self.p2p.register_handler('transaction', self._handle_received_tx)
        self.p2p.register_handler('ping', self._handle_ping)
        self.p2p.register_handler('pong', self._handle_pong)
        self.p2p.register_handler('get_peers', self._handle_get_peers)
        self.p2p.register_handler('peers', self._handle_peer_list)
        logger.info("Python P2P message handlers registered")

    async def _handle_received_block(self, message, sender_id):
        """Handle block received from peer"""
        try:
            block_data = message.data
            block_height = block_data.get('height')
            block_hash = str(block_data.get('hash', 'unknown'))[:16]
            logger.info(f"Received block from {sender_id}: height {block_height}, hash {block_hash}...")

            if not isinstance(block_height, int):
                logger.warning(f"Block from {sender_id} missing valid height, ignoring")
                return

            current_height = self.db.get_current_height()
            if block_height <= current_height:
                logger.debug(f"Already have block at height {block_height}, ignoring")
                return

            logger.info(f"Block {block_height} validated and ready to add")
            blocks_received.inc()

            # Process block knowledge for Aether Tree
            if hasattr(self, 'aether') and self.aether:
                try:
                    from .database.models import Block as BlockModel
                    block_obj = BlockModel.from_dict(block_data)
                    self.aether.process_block_knowledge(block_obj)
                except Exception as e:
                    logger.debug(f"Aether knowledge from peer block: {e}")

            if self.mining.is_mining and block_height > current_height:
                logger.info(f"New block found by peer, updating mining target")
        except Exception as e:
            logger.error(f"Error handling block from {sender_id}: {e}", exc_info=True)

    async def _handle_received_tx(self, message, sender_id):
        """Handle transaction received from peer"""
        try:
            tx_data = message.data
            tx_id = tx_data.get('txid', 'unknown')[:16]
            logger.info(f"Received transaction from {sender_id}: {tx_id}...")
            logger.debug(f"Transaction {tx_id} added to mempool")
        except Exception as e:
            logger.error(f"Error handling transaction from {sender_id}: {e}")

    async def _handle_ping(self, message, sender_id):
        """Respond to ping message"""
        logger.debug(f"Ping from {sender_id}")
        await self.p2p.send_message(sender_id, 'pong', {
            'timestamp': time.time(),
            'height': self.db.get_current_height()
        })

    async def _handle_pong(self, message, sender_id):
        """Handle pong response"""
        logger.debug(f"Pong from {sender_id}")
        peer_height = message.data.get('height', 0)
        our_height = self.db.get_current_height()
        if peer_height > our_height:
            logger.info(f"Peer {sender_id} has higher height: {peer_height} vs our {our_height}")

    async def _handle_get_peers(self, message, sender_id):
        """Handle request for peer list"""
        logger.debug(f"Peer {sender_id} requesting peer list")
        peer_list = self.p2p.get_peer_list()
        await self.p2p.send_message(sender_id, 'peers', peer_list)

    async def _handle_peer_list(self, message, sender_id):
        """Handle received peer list"""
        peers = message.data
        logger.info(f"Received {len(peers)} peers from {sender_id}")
        for peer_info in peers:
            peer_address = f"{peer_info['host']}:{peer_info['port']}"
            if peer_info.get('peer_id') == self.p2p.peer_id:
                continue
            if peer_address not in self.p2p.connections:
                asyncio.create_task(self.p2p.connect_to_peer(peer_address))

    async def _update_metrics_loop(self):
        """Periodically update Prometheus metrics from database"""
        logger.info("Metrics update loop started")

        while self.running:
            try:
                await self._update_all_metrics()
                await asyncio.sleep(30)  # Update every 30 seconds
            except Exception as e:
                logger.error(f"Error updating metrics: {e}", exc_info=True)
                await asyncio.sleep(30)

    def _start_rust_p2p_daemon(self) -> None:
        """Launch the Rust P2P daemon as a subprocess.

        Locates the binary, starts it with the configured ports, and waits
        for the gRPC health endpoint to become reachable before returning.
        Falls back to Python P2P if the daemon fails to start.
        """
        import shutil
        binary = Path(Config.RUST_P2P_BINARY)
        if not binary.is_absolute():
            # Resolve relative to project root (parent of src/)
            project_root = Path(__file__).resolve().parent.parent.parent
            binary = project_root / binary

        if not binary.exists():
            # Check if the binary is on PATH (e.g., in Docker: /usr/local/bin)
            on_path = shutil.which(binary.name)
            if on_path:
                binary = Path(on_path)
            else:
                logger.warning(f"Rust P2P binary not found at {binary} — falling back to Python P2P")
                Config.ENABLE_RUST_P2P = False
                return

        grpc_addr = f"127.0.0.1:{Config.RUST_P2P_GRPC}"
        env = {
            **os.environ,
            "P2P_PORT": str(Config.RUST_P2P_PORT),
            "RUST_P2P_GRPC_ADDR": grpc_addr,
        }
        if Config.BOOTSTRAP_PEERS:
            env["BOOTSTRAP_PEERS"] = Config.BOOTSTRAP_PEERS

        logger.info(f"Starting Rust P2P daemon: {binary}")
        logger.info(f"  P2P port: {Config.RUST_P2P_PORT}, gRPC: {grpc_addr}")

        try:
            self.rust_p2p_process = subprocess.Popen(
                [str(binary)],
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )
        except OSError as e:
            logger.error(f"Failed to launch Rust P2P daemon: {e}")
            Config.ENABLE_RUST_P2P = False
            return

        # Wait for gRPC to become reachable
        import grpc as _grpc
        deadline = time.time() + Config.RUST_P2P_STARTUP_TIMEOUT
        connected = False
        while time.time() < deadline:
            # Check process is still alive
            if self.rust_p2p_process.poll() is not None:
                logger.error(f"Rust P2P daemon exited with code {self.rust_p2p_process.returncode}")
                self.rust_p2p_process = None
                Config.ENABLE_RUST_P2P = False
                return
            try:
                channel = _grpc.insecure_channel(grpc_addr)
                _grpc.channel_ready_future(channel).result(timeout=1)
                channel.close()
                connected = True
                break
            except Exception as e:
                logger.debug(f"gRPC connect attempt: {e}")
                time.sleep(0.5)

        if connected:
            logger.info(f"Rust P2P daemon ready (PID {self.rust_p2p_process.pid})")
        else:
            logger.warning("Rust P2P daemon started but gRPC not reachable within timeout — continuing anyway")

    async def _update_all_metrics(self):
        """Update all Prometheus metrics from current state"""
        try:
            # ============================================================
            # BLOCKCHAIN METRICS
            # ============================================================
            height_row = self.db.query_one(
                "SELECT MAX(height) as best_height FROM blocks"
            )
            supply_row = self.db.query_one(
                "SELECT total_minted FROM supply WHERE id = 1"
            )

            if height_row and height_row.get('best_height') is not None:
                current_height_metric.set(height_row['best_height'])
            if supply_row:
                total_supply_metric.set(float(supply_row.get('total_minted', 0)))
            _mining_snap = self.mining.get_stats_snapshot()
            current_difficulty_metric.set(
                _mining_snap.get('current_difficulty', Config.INITIAL_DIFFICULTY)
            )

            # Average block time (last 100 blocks)
            block_time_row = self.db.query_one("""
                SELECT AVG(t2.timestamp - t1.timestamp) as avg_time
                FROM (SELECT height, timestamp FROM blocks ORDER BY height DESC LIMIT 101) t1
                JOIN (SELECT height, timestamp FROM blocks ORDER BY height DESC LIMIT 101) t2
                  ON t2.height = t1.height + 1
            """)
            if block_time_row and block_time_row.get('avg_time') is not None:
                avg_block_time_metric.set(float(block_time_row['avg_time']))

            # ============================================================
            # NETWORK METRICS
            # ============================================================
            if Config.ENABLE_RUST_P2P and self.rust_p2p:
                peer_count = self.rust_p2p.get_peer_count()
                rust_p2p_peers.set(peer_count)
                active_peers.set(peer_count)
            elif self.p2p:
                active_peers.set(len(self.p2p.connections))

            # ============================================================
            # TRANSACTION METRICS
            # ============================================================
            mempool_count = self.db.query_one(
                "SELECT COUNT(*) as count FROM transactions WHERE status = 'pending'"
            )
            if mempool_count:
                transactions_pending.set(mempool_count.get('count', 0))

            confirmed_count = self.db.query_one(
                "SELECT COUNT(*) as count FROM transactions WHERE status = 'confirmed'"
            )
            if confirmed_count:
                transactions_confirmed.set(confirmed_count.get('count', 0))

            # ============================================================
            # QUANTUM RESEARCH METRICS
            # ============================================================
            hamiltonian_stats = self.db.query_one(
                "SELECT COUNT(*) as total_count FROM solved_hamiltonians"
            )
            if hamiltonian_stats:
                active_hamiltonians.set(hamiltonian_stats.get('total_count', 0))
                vqe_solutions_total.set(hamiltonian_stats.get('total_count', 0))

            # ============================================================
            # QVM METRICS
            # ============================================================
            # Query both tables: accounts (EVM bytecode) + contracts (template)
            evm_stats = self.db.query_one("""
                SELECT COUNT(*) as cnt
                FROM accounts WHERE code_hash != '' AND code_hash IS NOT NULL
            """)
            template_stats = self.db.query_one("""
                SELECT
                    COUNT(*) as total,
                    COUNT(*) FILTER (WHERE is_active = true) as active_count
                FROM contracts
            """)
            evm_count = (evm_stats or {}).get('cnt', 0)
            tmpl_total = (template_stats or {}).get('total', 0)
            tmpl_active = (template_stats or {}).get('active_count', 0)
            total_contracts.set(evm_count + tmpl_total)
            active_contracts.set(evm_count + tmpl_active)

            # ============================================================
            # AGI METRICS
            # ============================================================
            latest_phi = self.db.query_one("""
                SELECT phi_value, phi_threshold, integration_score, differentiation_score
                FROM phi_measurements
                ORDER BY block_height DESC
                LIMIT 1
            """)

            if latest_phi:
                phi_val = float(latest_phi.get('phi_value', 0.1))
                phi_thresh = float(latest_phi.get('phi_threshold', 3.0))

                phi_current.set(phi_val)
                phi_threshold_distance.set(max(0, phi_thresh - phi_val))
                integration_score.set(float(latest_phi.get('integration_score', 0.1)))
                differentiation_score.set(float(latest_phi.get('differentiation_score', 0.1)))

                if phi_val > 0.1:
                    progress_pct = (phi_val / phi_thresh) * 100
                    logger.debug(f"Consciousness: Phi={phi_val:.4f} ({progress_pct:.1f}% to threshold)")

            knowledge_stats = self.db.query_one("""
                SELECT
                    (SELECT COUNT(*) FROM knowledge_nodes) as node_count,
                    (SELECT COUNT(*) FROM knowledge_edges) as edge_count
            """)
            if knowledge_stats:
                knowledge_nodes_total.set(knowledge_stats.get('node_count', 0))
                knowledge_edges_total.set(knowledge_stats.get('edge_count', 0))

            # Consciousness events + reasoning operations
            consciousness_count = self.db.query_one(
                "SELECT COUNT(*) as count FROM consciousness_events"
            )
            if consciousness_count:
                consciousness_events_total.set(consciousness_count.get('count', 0))

            reasoning_count = self.db.query_one(
                "SELECT COUNT(*) as count FROM reasoning_operations"
            )
            if reasoning_count:
                reasoning_operations_total.set(reasoning_count.get('count', 0))

            # ============================================================
            # IPFS METRICS
            # ============================================================
            ipfs_stats = self.db.query_one(
                "SELECT COUNT(*) as snapshots FROM ipfs_snapshots"
            )
            if ipfs_stats:
                blockchain_snapshots_total.set(ipfs_stats.get('snapshots', 0))

            # ============================================================
            # NEW SUBSYSTEM METRICS
            # ============================================================

            # Bridge
            if self.bridge_manager:
                try:
                    bridge_active_chains.set(len(self.bridge_manager.bridges))
                except Exception as e:
                    logger.debug(f"Metrics update error (bridge): {e}")
            subsystem_bridge_up.set(1 if self.bridge_manager else 0)

            # Compliance
            if self.compliance_engine:
                try:
                    policies = self.compliance_engine.list_policies()
                    compliance_policies_total.set(len(policies))
                    blocked = sum(1 for p in policies if getattr(p, 'is_blocked', False))
                    compliance_blocked_addresses.set(blocked)
                    cb = self.compliance_engine.circuit_breaker
                    compliance_circuit_breaker.set(1 if getattr(cb, 'is_tripped', False) else 0)
                except Exception as e:
                    logger.debug(f"Metrics update error (compliance): {e}")
                if self.compliance_engine and hasattr(self.compliance_engine, 'sanctions'):
                    try:
                        sanctions_entries_total.set(len(self.compliance_engine.sanctions._entries))
                    except Exception as e:
                        logger.debug(f"Metrics update error (sanctions): {e}")
            subsystem_compliance_up.set(1 if self.compliance_engine else 0)

            # Plugins
            if self.plugin_manager:
                try:
                    all_plugins = self.plugin_manager.list_plugins()
                    qvm_plugins_registered.set(len(all_plugins))
                    active_count = sum(1 for p in all_plugins if p.get('active', False))
                    qvm_plugins_active.set(active_count)
                except Exception as e:
                    logger.debug(f"Metrics update error (plugins): {e}")
            subsystem_plugins_up.set(1 if self.plugin_manager else 0)

            # QVM Extensions
            if self.state_channel_manager:
                try:
                    sc_stats = self.state_channel_manager.get_stats()
                    qvm_state_channels_open.set(sc_stats.get('open_channels', 0))
                    qvm_state_channels_tvl.set(float(sc_stats.get('total_locked_qbc', 0)))
                except Exception as e:
                    logger.debug(f"Metrics update error (state channels): {e}")
            if self.transaction_batcher:
                try:
                    b_stats = self.transaction_batcher.get_stats()
                    qvm_batch_pending_txs.set(b_stats.get('pending_transactions', 0))
                except Exception as e:
                    logger.debug(f"Metrics update error (tx batcher): {e}")
            if self.decoherence_manager:
                try:
                    d_stats = self.decoherence_manager.get_stats()
                    qvm_decoherence_active.set(d_stats.get('active_states', 0))
                except Exception as e:
                    logger.debug(f"Metrics update error (decoherence): {e}")
            if self.tlac_manager:
                try:
                    t_stats = self.tlac_manager.get_stats()
                    tlac_pending.set(t_stats.get('pending', 0))
                except Exception as e:
                    logger.debug(f"Metrics update error (TLAC): {e}")

            # Stablecoin
            if self.stablecoin_engine:
                try:
                    sc_info = self.stablecoin_engine.get_system_health()
                    qusd_total_supply.set(float(sc_info.get('total_qusd', 0)))
                    qusd_reserve_backing_pct.set(float(sc_info.get('reserve_backing', 0)))
                    qusd_active_vaults.set(sc_info.get('active_vaults', 0))
                    qusd_total_debt.set(float(sc_info.get('cdp_debt', 0)))
                except Exception as e:
                    logger.debug(f"Metrics update error (stablecoin): {e}")
            subsystem_stablecoin_up.set(1 if self.stablecoin_engine else 0)

            # Cognitive Architecture
            if self.sephirot_manager:
                try:
                    s_status = self.sephirot_manager.get_status()
                    sephirot_active_nodes.set(s_status.get('active_nodes', 10))
                except Exception as e:
                    logger.debug(f"Metrics update error (sephirot): {e}")
            if self.csf_transport:
                try:
                    csf_stats = self.csf_transport.get_stats()
                    csf_queue_depth.set(csf_stats.get('queue_depth', 0))
                except Exception as e:
                    logger.debug(f"Metrics update error (CSF transport): {e}")
            if self.pineal_orchestrator:
                try:
                    p_status = self.pineal_orchestrator.get_status()
                    pineal_current_phase.set(p_status.get('phase_index', 0))
                    pineal_metabolic_rate.set(float(p_status.get('metabolic_rate', 1.0)))
                    pineal_is_conscious.set(1 if p_status.get('is_conscious', False) else 0)
                except Exception as e:
                    logger.debug(f"Metrics update error (pineal): {e}")
            subsystem_cognitive_up.set(1 if self.sephirot_manager else 0)

            # Higgs Cognitive Field
            if self.higgs_field:
                try:
                    h_status = self.higgs_field.get_status()
                    higgs_field_value.set(h_status.get('field_value', 0))
                    higgs_vev.set(h_status.get('vev', 0))
                    higgs_deviation_pct.set(h_status.get('deviation_pct', 0))
                    higgs_mass_gap.set(h_status.get('mass_gap', 0))
                    higgs_excitations_total.inc(0)  # Counter: just keep alive
                    masses = self.higgs_field._cognitive_masses
                    if masses:
                        higgs_avg_cognitive_mass.set(
                            sum(masses.values()) / len(masses)
                        )
                    higgs_potential_energy.set(h_status.get('potential_energy', 0))
                except Exception as e:
                    logger.debug(f"Metrics update error (Higgs field): {e}")

            # Fee Collector
            if self.fee_collector:
                try:
                    fc_stats = self.fee_collector.get_stats()
                    fees_collected_total.set(fc_stats.get('total_events', 0))
                    fees_collected_qbc_total.set(float(fc_stats.get('total_collected', 0)))
                except Exception as e:
                    logger.debug(f"Metrics update error (fee collector): {e}")

            # QUSD Oracle
            if self.qusd_oracle:
                try:
                    o_status = self.qusd_oracle.get_status()
                    qusd_price_qbc_usd.set(float(o_status.get('qbc_usd_price', 0)))
                    qusd_oracle_stale.set(1 if o_status.get('is_stale', True) else 0)
                except Exception as e:
                    logger.debug(f"Metrics update error (QUSD oracle): {e}")

            # Capability
            if self.capability_advertiser:
                try:
                    c_summary = self.capability_advertiser.get_network_summary()
                    capability_active_peers.set(c_summary.get('total_peers', 0))
                    capability_total_mining_power.set(float(c_summary.get('total_mining_power', 0)))
                except Exception as e:
                    logger.debug(f"Metrics update error (capability): {e}")

            # IPFS Memory
            if self.ipfs_memory:
                try:
                    m_stats = self.ipfs_memory.get_stats()
                    ipfs_memory_cache_size.set(m_stats.get('cache_size', 0))
                except Exception as e:
                    logger.debug(f"Metrics update error (IPFS memory): {e}")

            # Privacy — static classes, always up
            subsystem_privacy_up.set(1)

            # ============================================================
            # AIKGS METRICS (via Rust sidecar gRPC)
            # ============================================================
            if self.aikgs_client and self.aikgs_client.connected:
                try:
                    import asyncio
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        # Schedule the async call — metrics will update next cycle
                        asyncio.ensure_future(self._update_aikgs_metrics())
                    else:
                        loop.run_until_complete(self._update_aikgs_metrics())
                except Exception as e:
                    logger.debug(f"Metrics update error (AIKGS): {e}")

        except Exception as e:
            logger.error(f"Error in _update_all_metrics: {e}", exc_info=True)

    async def on_startup(self):
        """Called when RPC server starts"""
        console.print(Panel.fit(
            "[bold green]Qubitcoin Full Node Starting[/]",
            border_style="green"
        ))

        height = self.db.get_current_height()
        balance = self.db.get_balance(Config.ADDRESS)
        supply = self.db.get_total_supply()

        logger.info("=" * 60)
        logger.info(f"Node Address: {Config.ADDRESS}")
        logger.info(f"Current Height: {height}")
        logger.info(f"Node Balance: {balance} QBC")
        logger.info(f"Total Supply: {supply} QBC")
        logger.info("=" * 60)

        # Validate critical config before launch
        if not Config.AETHER_FEE_TREASURY_ADDRESS:
            logger.warning("AETHER_FEE_TREASURY_ADDRESS not set — Aether chat fees will not be collected")
        if not Config.CONTRACT_FEE_TREASURY_ADDRESS:
            logger.warning("CONTRACT_FEE_TREASURY_ADDRESS not set — contract deployment fees will not be collected")
        if not Config.ADDRESS:
            logger.error("NODE ADDRESS not set — run scripts/setup/generate_keys.py first")

        # Initial metrics
        current_height_metric.set(height)
        total_supply_metric.set(float(supply))

        # Set quantum backend metric
        if Config.USE_LOCAL_ESTIMATOR:
            quantum_backend_metric.set(0)
        elif Config.USE_SIMULATOR:
            quantum_backend_metric.set(1)
        else:
            quantum_backend_metric.set(2)

        # Start P2P network
        if Config.ENABLE_RUST_P2P:
            logger.info("Connecting to Rust P2P network...")
            if self.rust_p2p.connect():
                peer_count = self.rust_p2p.get_peer_count()
                logger.info(f"Rust P2P connected - {peer_count} peers")
                rust_p2p_peers.set(peer_count)
                # Start streaming blocks/txs from Rust P2P
                await self.rust_p2p.start_streaming(
                    on_block=self._on_p2p_block_received,
                    on_tx=self._on_p2p_tx_received,
                )
                logger.info("Rust P2P block/tx streaming started")
            else:
                logger.warning("Rust P2P connection failed - running without P2P")
        else:
            await self.p2p.start()
            logger.info(f"Python P2P network started on port {Config.P2P_PORT}")

            if Config.PEER_SEEDS:
                logger.info(f"Connecting to {len(Config.PEER_SEEDS)} seed peers...")
                for seed in Config.PEER_SEEDS:
                    if seed and seed.strip():
                        asyncio.create_task(self.p2p.connect_to_peer(seed.strip()))
                        await asyncio.sleep(1)
            else:
                logger.info("No seed peers configured (bootstrap node)")

        # Start metrics update loop
        self.running = True
        self.metrics_task = asyncio.create_task(self._update_metrics_loop())
        logger.info("Metrics collection started")

        # Start knowledge seeder
        if self.knowledge_seeder:
            self.knowledge_seeder.start()
            logger.info("Knowledge seeder started")

        # Initialize bridges (async)
        if self.bridge_manager:
            try:
                await self.bridge_manager.initialize_bridges()
                logger.info("Bridge manager bridges initialized")
            except Exception as e:
                logger.warning(f"Bridge initialization failed (non-fatal): {e}")

        # Seed capability advertiser with VQE capability
        if self.capability_advertiser:
            try:
                from .mining.capability_detector import VQECapabilityDetector
                detector = VQECapabilityDetector()
                detector.detect(self.quantum)
                ad = detector.get_p2p_advertisement()
                if ad:
                    self.capability_advertiser.set_local_capability(ad)
                    logger.info("Capability advertiser seeded with VQE capability")
            except Exception as e:
                logger.debug(f"Capability seeding: {e}")

        # Connect to AIKGS Rust sidecar
        if self.aikgs_client:
            connected = await self.aikgs_client.connect()
            if connected:
                logger.info("AIKGS Rust sidecar connected")
            else:
                logger.warning("AIKGS Rust sidecar not reachable — AIKGS features unavailable")

        # Start mining
        if Config.AUTO_MINE:
            self.mining.start()

        # Snapshot check
        if height > 0 and height % Config.SNAPSHOT_INTERVAL == 0:
            loop = asyncio.get_event_loop()
            loop.run_in_executor(None, self.ipfs.create_snapshot, self.db, height)

        logger.info("Node startup complete")

    async def on_shutdown(self):
        """Called when RPC server stops"""
        logger.info("Shutting down node...")
        self.running = False

        # Stop metrics task
        if self.metrics_task:
            self.metrics_task.cancel()
            try:
                await self.metrics_task
            except asyncio.CancelledError:
                pass

        # Stop knowledge seeder
        if self.knowledge_seeder:
            self.knowledge_seeder.stop()

        self.mining.stop()

        # Close AIKGS sidecar client
        if self.aikgs_client:
            try:
                await self.aikgs_client.close()
            except Exception as e:
                logger.debug(f"AIKGS client close: {e}")

        # Shutdown bridges
        if self.bridge_manager:
            try:
                await self.bridge_manager.shutdown()
            except Exception as e:
                logger.debug(f"Bridge shutdown: {e}")

        # Stop all plugins
        if self.plugin_manager:
            try:
                for plugin_info in self.plugin_manager.list_plugins():
                    try:
                        self.plugin_manager.stop(plugin_info['name'])
                    except Exception as e:
                        logger.debug(f"Plugin stop error ({plugin_info.get('name', '?')}): {e}")
            except Exception as e:
                logger.debug(f"Plugin shutdown: {e}")

        if self.rust_p2p:
            self.rust_p2p.disconnect()
        if self.rust_p2p_process:
            logger.info(f"Stopping Rust P2P daemon (PID {self.rust_p2p_process.pid})...")
            self.rust_p2p_process.terminate()
            try:
                self.rust_p2p_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                logger.warning("Rust P2P daemon did not stop in time, killing...")
                self.rust_p2p_process.kill()
                self.rust_p2p_process.wait(timeout=2)
            self.rust_p2p_process = None
        if self.p2p:
            await self.p2p.stop()

        console.print(Panel.fit(
            "[bold yellow]Qubitcoin Node Stopped[/]",
            border_style="yellow"
        ))
        logger.info("Node shutdown complete")

    async def _update_aikgs_metrics(self) -> None:
        """Fetch AIKGS stats from the Rust sidecar and update Prometheus gauges."""
        try:
            stats = await self.aikgs_client.get_full_stats()
            c = stats.get('contributions', {})
            aikgs_total_contributions.set(c.get('total_contributions', 0))
            aikgs_unique_contributors.set(c.get('unique_contributors', 0))
            tier_dist = c.get('tier_distribution', {})
            aikgs_tier_bronze.set(tier_dist.get('bronze', 0))
            aikgs_tier_silver.set(tier_dist.get('silver', 0))
            aikgs_tier_gold.set(tier_dist.get('gold', 0))
            aikgs_tier_diamond.set(tier_dist.get('diamond', 0))
            r = stats.get('rewards', {})
            aikgs_total_rewards_distributed.set(r.get('total_distributed', 0))
            aikgs_pool_balance.set(r.get('pool_balance', 0))
            a = stats.get('affiliates', {})
            aikgs_affiliates_total.set(a.get('total_affiliates', 0))
            aikgs_commissions_total.set(
                a.get('total_l1_commissions', 0) + a.get('total_l2_commissions', 0)
            )
            b = stats.get('bounties', {})
            aikgs_bounties_active.set(b.get('open_bounties', 0))
            cu = stats.get('curation', {})
            aikgs_curation_pending.set(
                cu.get('status_distribution', {}).get('pending', 0)
            )
        except Exception as e:
            logger.debug(f"AIKGS metrics update error: {e}")

    async def _on_p2p_block_received(self, block_data: dict) -> None:
        """Handle a block received from the Rust P2P stream."""
        try:
            height = block_data.get('height', 0)
            block_hash = block_data.get('hash', '')
            logger.info(f"P2P block received: height={height} hash={block_hash[:16]}...")

            blocks_received.inc()

            # Validate and add to chain via consensus
            if self.consensus:
                valid = self.consensus.validate_block(block_data)
                if valid:
                    logger.info(f"P2P block {height} validated, adding to chain")
                    current_height_metric.set(height)
                else:
                    logger.warning(f"P2P block {height} failed validation")
            else:
                logger.debug(f"No consensus engine — skipping P2P block {height}")

        except Exception as e:
            logger.error(f"Error processing P2P block: {e}")

    async def _on_p2p_tx_received(self, tx_data: dict) -> None:
        """Handle a transaction received from the Rust P2P stream."""
        try:
            txid = tx_data.get('txid', '')
            logger.debug(f"P2P tx received: {txid[:8]}...")

            # Add to mempool if available
            if hasattr(self, 'mining') and self.mining:
                logger.debug(f"P2P tx {txid[:8]} would be added to mempool")

        except Exception as e:
            logger.error(f"Error processing P2P tx: {e}")

    def on_block_mined(self, block_data: dict) -> None:
        """Called when mining engine successfully mines a block"""
        try:
            block_height = block_data.get('height', 'unknown')
            block_hash = block_data.get('hash', 'unknown')

            logger.info(f"Block {block_height} mined! Broadcasting to network...")

            # Update metrics
            blocks_mined.inc()
            current_height_metric.set(block_height)

            # Update alignment score if present
            alignment = block_data.get('alignment_score', 0)
            if alignment:
                alignment_score_metric.set(float(alignment))

            if Config.ENABLE_RUST_P2P and self.rust_p2p:
                # Use Rust P2P for broadcasting
                success = self.rust_p2p.broadcast_block(block_height, block_hash)
                if success:
                    peer_count = self.rust_p2p.get_peer_count()
                    logger.info(f"Block {block_height} broadcasted via Rust P2P to {peer_count} peers")
                else:
                    logger.warning(f"Failed to broadcast block {block_height} via Rust P2P")
            elif self.p2p:
                # Use Python P2P for broadcasting
                asyncio.create_task(self.p2p.broadcast('block', block_data))
                peer_count = len(self.p2p.connections)
                logger.info(f"Block {block_height} broadcasted via Python P2P to {peer_count} peers")
            else:
                logger.warning("No P2P network available - block not broadcasted")

            # Broadcast to WebSocket clients for real-time updates
            if hasattr(self.app, 'broadcast_ws'):
                ws_data = {
                    'height': block_height,
                    'hash': block_hash,
                    'timestamp': block_data.get('timestamp', 0),
                    'miner': block_data.get('miner', ''),
                    'reward': block_data.get('reward', 0),
                    'tx_count': block_data.get('tx_count', 0),
                }
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        asyncio.ensure_future(self.app.broadcast_ws('new_block', ws_data))
                    else:
                        loop.run_until_complete(self.app.broadcast_ws('new_block', ws_data))
                except RuntimeError:
                    # No event loop in mining thread — expected; clients will poll instead
                    logger.debug("No event loop for WebSocket broadcast (mining thread)")

        except Exception as e:
            logger.error(f"Error broadcasting mined block: {e}")

    def run(self) -> None:
        """Run the node"""
        import uvicorn

        def signal_handler(signum: int, frame: object) -> None:
            logger.info(f"Received signal {signum}, shutting down...")
            sys.exit(0)

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        uvicorn.run(
            self.app,
            host=Config.RPC_HOST,
            port=Config.RPC_PORT,
            log_level=Config.LOG_LEVEL.lower(),
            access_log=Config.DEBUG
        )

def main() -> None:
    """Main entry point"""
    try:
        node = QubitcoinNode()
        node.run()
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
