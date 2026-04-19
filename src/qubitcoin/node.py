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
from .network.chain_sync import ChainSync
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
    # AI
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
    # QUSD Keeper
    qusd_keeper_mode, qusd_keeper_last_check_block,
    qusd_keeper_stability_fund, qusd_keeper_max_deviation,
    qusd_keeper_paused, qusd_keeper_arb_opportunities,
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

        # Component 3: P2P / Substrate Bridge
        self.substrate_bridge = None
        if Config.SUBSTRATE_MODE:
            # In Substrate mode, P2P is handled by Substrate node
            logger.info("[3/22] SUBSTRATE_MODE=true — P2P handled by Substrate node")
            self.p2p = None
            self.rust_p2p = None
            try:
                from .substrate_bridge import SubstrateBridge
                self.substrate_bridge = SubstrateBridge()
                logger.info(f"[3/22] SubstrateBridge initialized (WS: {Config.SUBSTRATE_WS_URL})")
            except Exception as e:
                logger.error(f"[3/22] SubstrateBridge failed: {e}", exc_info=True)
                raise
        else:
            logger.info("[3/22] Initializing P2P Network...")
            try:
                if Config.ENABLE_RUST_P2P:
                    logger.info("Using Rust P2P (libp2p 0.56)")
                    if Config.RUST_P2P_GRPC_HOST:
                        # Connect to external P2P daemon (separate container)
                        grpc_target = f"{Config.RUST_P2P_GRPC_HOST}:{Config.RUST_P2P_GRPC}"
                        logger.info(f"Connecting to external Rust P2P at {grpc_target}")
                    else:
                        # Launch subprocess (legacy single-container mode)
                        self._start_rust_p2p_daemon()
                        grpc_target = f"127.0.0.1:{Config.RUST_P2P_GRPC}"
                    self.rust_p2p = RustP2PClient(grpc_target)
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

        # Component 7: Aether Tree (AI layer)
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

            # Initialize AI from genesis if this is the first run
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

            # Phase 6: On-chain AI integration
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

        # Component 7a: AI Persistence — load learned state from DB
        self.agi_persistence = None
        try:
            from .aether.persistence import AGIPersistence
            self.agi_persistence = AGIPersistence(self.db)
            self._load_agi_state()
            logger.info("[7a/22] AI Persistence initialized — learned state loaded")
        except Exception as e:
            logger.warning(f"[7a/22] AI Persistence failed (non-fatal): {e}")

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
                    OllamaAdapter, BitNetAdapter,
                )
                self.llm_manager = LLMAdapterManager(self.knowledge_graph)

                # Register adapters in priority order based on LLM_PRIMARY_ADAPTER
                primary = Config.LLM_PRIMARY_ADAPTER
                adapters_to_register = []

                # BitNet local inference (highest priority when available)
                bitnet_url = getattr(Config, 'BITNET_BASE_URL', 'http://127.0.0.1:8178/v1')
                bitnet_adapter = BitNetAdapter(base_url=bitnet_url)
                if bitnet_adapter.is_available():
                    adapters_to_register.append((
                        bitnet_adapter,
                        5 if primary == 'bitnet' else 15,
                    ))
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
                if Config.OLLAMA_BASE_URL:
                    adapters_to_register.append((
                        OllamaAdapter(
                            model=Config.OLLAMA_MODEL,
                            base_url=Config.OLLAMA_BASE_URL,
                            max_tokens=200,  # 200 tokens → ~15 facts per seed call on CPU Ollama
                        ),
                        10 if primary == 'ollama' else 30,
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

        # Component 14b: QUSD Keeper (peg monitoring + stabilization)
        self.qusd_keeper = None
        self.dex_price_reader = None
        self.arb_calculator = None
        if Config.KEEPER_ENABLED:
            try:
                from .stablecoin.dex_price import DEXPriceReader
                self.dex_price_reader = DEXPriceReader()
                logger.info("[14b/22] DEXPriceReader initialized")
            except Exception as e:
                logger.debug(f"DEXPriceReader init: {e}")
            try:
                from .stablecoin.arbitrage import ArbitrageCalculator
                self.arb_calculator = ArbitrageCalculator(self.dex_price_reader)
                logger.info("[14b/22] ArbitrageCalculator initialized")
            except Exception as e:
                logger.debug(f"ArbitrageCalculator init: {e}")
            try:
                from .stablecoin.keeper import QUSDKeeper, KeeperMode
                self.qusd_keeper = QUSDKeeper(
                    stablecoin_engine=self.stablecoin_engine,
                    qvm=self.state_manager,
                    dex_reader=self.dex_price_reader,
                    arb_calc=self.arb_calculator,
                )
                # Start in configured default mode
                mode_map = {
                    'off': KeeperMode.OFF, 'scan': KeeperMode.SCAN,
                    'periodic': KeeperMode.PERIODIC, 'continuous': KeeperMode.CONTINUOUS,
                    'aggressive': KeeperMode.AGGRESSIVE,
                }
                default_mode = mode_map.get(Config.KEEPER_DEFAULT_MODE.lower(), KeeperMode.SCAN)
                # Set role from config (primary executes, observer only scans)
                keeper_role = getattr(Config, 'KEEPER_ROLE', 'primary').lower()
                self.qusd_keeper.config.role = keeper_role
                # Observer nodes are forced to scan mode regardless of config
                if keeper_role == "observer":
                    default_mode = KeeperMode.SCAN
                self.qusd_keeper.start(default_mode)
                logger.info(f"[14b/22] QUSDKeeper initialized (mode={default_mode.name}, role={keeper_role})")
            except Exception as e:
                logger.warning(f"[14b/22] QUSDKeeper init failed (non-fatal): {e}")

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

        # Component 19b: Exchange Engine — Rust primary, Python fallback
        self.exchange_engine = None
        self.rust_exchange_client = None
        try:
            from .exchange.rust_exchange_client import RustExchangeClient
            exchange_grpc = os.environ.get("EXCHANGE_GRPC", "127.0.0.1:50053")
            self.rust_exchange_client = RustExchangeClient(exchange_grpc)
            if self.rust_exchange_client.connect():
                logger.info(f"[19b/22] Rust Exchange connected at {exchange_grpc}")
            else:
                logger.warning("[19b/22] Rust Exchange not available, using Python fallback")
                self.rust_exchange_client = None
        except Exception as e:
            logger.debug(f"Rust Exchange client init: {e}")
            self.rust_exchange_client = None

        try:
            from .exchange.engine import ExchangeEngine
            self.exchange_engine = ExchangeEngine(db_manager=self.db)
            logger.info("[19b/22] ExchangeEngine initialized (Python fallback, db_manager wired)")
        except Exception as e:
            logger.error(f"ExchangeEngine init failed: {e}", exc_info=True)

        # Component 19c: Reversibility Manager
        self.reversibility_manager = None
        try:
            from .reversibility.manager import ReversibilityManager
            self.reversibility_manager = ReversibilityManager(
                self.db,
                default_window=Config.REVERSAL_DEFAULT_WINDOW,
            )
            logger.info("[19c/22] ReversibilityManager initialized")
        except Exception as e:
            logger.debug(f"[19c/22] ReversibilityManager init: {e}")

        # Component 19e: Inheritance Manager
        self.inheritance_manager = None
        if Config.INHERITANCE_ENABLED:
            try:
                from .reversibility.inheritance import InheritanceManager
                self.inheritance_manager = InheritanceManager(self.db)
                logger.info("[19e/22] InheritanceManager initialized")
            except Exception as e:
                logger.debug(f"[19e/22] InheritanceManager init: {e}")

        # Component 19h: Deniable RPC Handler
        self.deniable_rpc = None
        if Config.DENIABLE_RPC_ENABLED:
            try:
                from .privacy.deniable_rpc import DeniableRPCHandler
                self.deniable_rpc = DeniableRPCHandler(self.db)
                logger.info("[19h/22] DeniableRPCHandler initialized")
            except Exception as e:
                logger.debug(f"[19h/22] DeniableRPCHandler init: {e}")

        # Component 19g: Stratum Bridge
        self.stratum_bridge = None
        if Config.STRATUM_ENABLED:
            try:
                from .mining.stratum_bridge import StratumBridgeService
                self.stratum_bridge = StratumBridgeService(
                    mining_engine=self.mining,
                    consensus_engine=self.consensus,
                    db_manager=self.db,
                )
                logger.info("[19g/22] StratumBridge initialized")
            except Exception as e:
                logger.debug(f"[19g/22] StratumBridge init: {e}")

        # Component 19f: High-Security Manager
        self.high_security_manager = None
        if Config.SECURITY_POLICY_ENABLED:
            try:
                from .reversibility.high_security import HighSecurityManager
                self.high_security_manager = HighSecurityManager(self.db)
                logger.info("[19f/22] HighSecurityManager initialized")
            except Exception as e:
                logger.debug(f"[19f/22] HighSecurityManager init: {e}")

        # Component 19i: BFT Finality Gadget
        self.finality_gadget = None
        if Config.FINALITY_ENABLED:
            try:
                from .consensus.finality import FinalityGadget
                self.finality_gadget = FinalityGadget(self.db)
                self.consensus.finality_gadget = self.finality_gadget
                logger.info("[19i/22] FinalityGadget initialized")
            except Exception as e:
                logger.debug(f"[19i/22] FinalityGadget init: {e}")

        # Component 19d: FIPS 204 KAT Self-Test
        try:
            from .quantum.fips204_kat import run_kat_tests
            from .quantum.crypto import _LEVEL_NAMES, SecurityLevel
            level = Config.get_security_level()
            kat_passed = run_kat_tests()
            if kat_passed:
                logger.info(
                    f"[19d/22] FIPS 204 KAT: PASSED — "
                    f"Dilithium security level: {_LEVEL_NAMES[level]} (LEVEL{level.value})"
                )
            else:
                logger.warning("[19d/22] FIPS 204 KAT: FAILED — crypto self-test errors detected")
        except Exception as e:
            logger.debug(f"[19d/22] FIPS 204 KAT: {e}")

        # Component 20: Mining Engine
        logger.info("[20/22] Initializing MiningEngine...")
        try:
            self.mining = MiningEngine(self.quantum, self.consensus, self.db, console,
                                       state_manager=self.state_manager,
                                       aether_engine=self.aether,
                                       substrate_bridge=self.substrate_bridge)
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

        # Component 21b: L1↔L2 Internal Bridge
        try:
            from .l2_bridge import L1L2Bridge
            self.l1l2_bridge = L1L2Bridge(self.db)
            logger.info("L1L2Bridge initialized (deposit/withdraw between UTXO and QVM accounts)")
        except Exception as e:
            self.l1l2_bridge = None
            logger.warning(f"L1L2Bridge init skipped: {e}")

        # Chain Sync (uses db, consensus, aether — no separate component number)
        self.chain_sync = ChainSync(
            self.db, self.consensus, self.aether,
            ipfs_manager=self.ipfs, mining_engine=self.mining
        )
        # Register peer URL from environment if set
        sync_peer = os.environ.get('SYNC_PEER_URL', '').strip()
        if sync_peer:
            self.chain_sync.add_peer_url(sync_peer)
            logger.info(f"Chain sync peer configured: {sync_peer}")

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
                rust_exchange_client=self.rust_exchange_client,
                higgs_field=self.higgs_field,
                # AIKGS (Rust sidecar gRPC client)
                aikgs_client=self.aikgs_client,
                aikgs_telegram_bot=self.aikgs_telegram_bot,
                substrate_bridge=self.substrate_bridge,
                qusd_keeper=self.qusd_keeper,
                dex_price_reader=self.dex_price_reader,
                arb_calculator=self.arb_calculator,
                reversibility_manager=self.reversibility_manager,
                inheritance_manager=self.inheritance_manager,
                high_security_manager=self.high_security_manager,
                stratum_bridge_service=self.stratum_bridge,
                deniable_rpc=self.deniable_rpc,
                finality_gadget=self.finality_gadget,
                l1l2_bridge=self.l1l2_bridge,
            )
            self.app.node = self
            self.app.on_event("startup")(self.on_startup)
            self.app.on_event("shutdown")(self.on_shutdown)

            # Wire RPC-created trackers back into engines so they receive data
            if self.aether and hasattr(self.app, 'consciousness_dashboard'):
                self.aether.consciousness_dashboard = self.app.consciousness_dashboard
            if self.aether and hasattr(self.app, 'pot_explorer'):
                self.aether.pot_explorer = self.app.pot_explorer
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

    # ──────────────────────────────────────────────────────────────────────
    # Substrate block processing (SUBSTRATE_MODE)
    # ──────────────────────────────────────────────────────────────────────

    async def _on_substrate_block_finalized(
        self,
        block_height: int,
        block_hash: str,
        header: dict,
        block_data: dict,
    ) -> None:
        """Process a finalized Substrate block through the Python execution pipeline.

        Called by SubstrateBridge for each new finalized block.
        Uses loop.run_in_executor with a dedicated single-worker pool
        so the main event loop stays responsive for API requests.
        """
        loop = asyncio.get_running_loop()
        if not hasattr(self, '_substrate_executor'):
            import concurrent.futures
            self._substrate_executor = concurrent.futures.ThreadPoolExecutor(
                max_workers=1, thread_name_prefix="substrate-block"
            )
        await loop.run_in_executor(
            self._substrate_executor,
            self._process_substrate_block_sync,
            block_height, block_hash, header, block_data,
        )

    def _process_substrate_block_sync(
        self,
        block_height: int,
        block_hash: str,
        header: dict,
        block_data: dict,
    ) -> None:
        """Synchronous block processing (runs in thread pool)."""
        try:
            from .substrate_codec import substrate_block_to_python
            from .database.models import Block as BlockModel

            logger.info(f"Processing Substrate block #{block_height} ({block_hash[:18]}...)")

            # Convert Substrate block to Python format
            py_block = substrate_block_to_python(
                block_height, block_hash, header, block_data
            )

            # Store block in CockroachDB (for RPC queries)
            try:
                block_obj = BlockModel(
                    height=py_block["height"],
                    block_hash=py_block["block_hash"],
                    prev_hash=py_block["prev_hash"],
                    timestamp=py_block["timestamp"],
                    difficulty=py_block["difficulty"],
                    state_root=py_block.get("state_root", ""),
                    transactions=[],
                    proof_data={},
                )

                with self.db.get_session() as session:
                    from sqlalchemy import text
                    existing = session.execute(
                        text("SELECT 1 FROM blocks WHERE height = :h"),
                        {'h': block_height}
                    ).first()
                    if not existing:
                        self.db.store_block(block_obj, session=session)
                        session.commit()
                        logger.debug(f"Block #{block_height} stored in CockroachDB")
                    else:
                        logger.debug(f"Block #{block_height} already in CockroachDB")
            except Exception as e:
                logger.error(f"Failed to store block #{block_height}: {e}", exc_info=True)

            # Update metrics
            current_height_metric.set(block_height)
            blocks_received.inc()

            # Heavy Aether processing only every 100th Substrate block
            # (at 3.3s blocks, this is ~5.5 min between full reasoning cycles).
            # This prevents GIL contention from starving the API event loop.
            # All blocks are still stored in CockroachDB above.
            if block_height % 100 == 0:
                # Process block knowledge for Aether Tree
                if self.aether:
                    try:
                        self.aether.process_block_knowledge(block_obj)
                    except Exception as e:
                        logger.debug(f"Aether knowledge processing: {e}")

                # Higgs Cognitive Field tick
                if getattr(self, 'higgs_field', None):
                    try:
                        self.higgs_field.tick(block_height)
                    except Exception as e:
                        logger.debug(f"Higgs field tick: {e}")

                # QUSD Keeper tick
                if getattr(self, 'qusd_keeper', None):
                    try:
                        self.qusd_keeper.on_block(block_height)
                    except Exception as e:
                        logger.debug(f"QUSD keeper tick: {e}")

            # Anchor Aether state back to Substrate (every 100 blocks)
            # Note: anchoring is async, schedule from sync thread via event loop
            if self.substrate_bridge and block_height % 100 == 0 and self.aether:
                try:
                    phi_value = self.aether.phi
                    kg = self.aether.kg
                    knowledge_root = kg.compute_merkle_root() if hasattr(kg, 'compute_merkle_root') else "0" * 64
                    n_nodes = len(kg.nodes) if hasattr(kg, 'nodes') else 0
                    n_edges = len(kg.edges) if hasattr(kg, 'edges') else 0

                    loop = asyncio.get_event_loop()
                    asyncio.run_coroutine_threadsafe(
                        self.substrate_bridge.anchor_aether_state(
                            block_height=block_height,
                            phi_value=phi_value,
                            knowledge_root=knowledge_root,
                            knowledge_nodes=n_nodes,
                            knowledge_edges=n_edges,
                        ),
                        loop,
                    )
                except Exception as e:
                    logger.debug(f"Aether anchoring: {e}")

            # Anchor QVM state root (every N blocks)
            if self.substrate_bridge and block_height % 100 == 0 and self.state_manager:
                try:
                    state_root = self.state_manager.get_state_root()
                    loop = asyncio.get_event_loop()
                    asyncio.run_coroutine_threadsafe(
                        self.substrate_bridge.anchor_qvm_state(
                            block_height=block_height,
                            state_root=state_root,
                        ),
                        loop,
                    )
                except Exception as e:
                    logger.debug(f"QVM state anchoring: {e}")

        except Exception as e:
            logger.error(
                f"Error processing Substrate block #{block_height}: {e}",
                exc_info=True,
            )

    def _load_agi_state(self) -> None:
        """Load persisted AI state from DB into Aether subsystems."""
        if not self.agi_persistence or not self.aether:
            return
        loaded = []
        try:
            if self.aether.neural_reasoner:
                if self.aether.neural_reasoner.load_weights(self.agi_persistence):
                    loaded.append('neural_reasoner')
            if self.aether.memory_manager:
                if self.aether.memory_manager.load_from_db(self.agi_persistence):
                    loaded.append('memory_manager')
            if self.aether.metacognition:
                if self.aether.metacognition.load_from_db(self.agi_persistence):
                    loaded.append('metacognition')
            if self.aether.temporal_engine:
                if self.aether.temporal_engine.load_from_persistence(self.agi_persistence):
                    loaded.append('temporal_engine')
            if loaded:
                logger.info("AI state loaded from DB: %s", ', '.join(loaded))
            else:
                logger.info("No persisted AI state found (fresh start)")
        except Exception as e:
            logger.warning("AI state load error (non-fatal): %s", e)

    def _save_agi_state(self, block_height: int) -> None:
        """Save AI state to DB (called every 100 blocks)."""
        if not self.agi_persistence or not self.aether:
            return
        saved = []
        try:
            if self.aether.neural_reasoner:
                if self.aether.neural_reasoner.save_weights(self.agi_persistence, block_height):
                    saved.append('neural_reasoner')
            if self.aether.memory_manager:
                if self.aether.memory_manager.save_to_db(self.agi_persistence, block_height):
                    saved.append('memory_manager')
            if self.aether.metacognition:
                if self.aether.metacognition.save_to_db(self.agi_persistence, block_height):
                    saved.append('metacognition')
            if self.aether.temporal_engine:
                if self.aether.temporal_engine.save_to_db(self.agi_persistence):
                    saved.append('temporal_engine')
            if saved:
                logger.info("AI state saved at block %d: %s", block_height, ', '.join(saved))
        except Exception as e:
            logger.warning("AI state save error (non-fatal): %s", e)

    async def _update_metrics_loop(self):
        """Periodically update Prometheus metrics from database.

        Runs the actual metrics collection in a thread pool to avoid blocking
        the asyncio event loop with synchronous DB queries.
        """
        logger.info("Metrics update loop started")
        loop = asyncio.get_running_loop()

        while self.running:
            try:
                await loop.run_in_executor(None, self._update_all_metrics_sync)
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

    def _update_all_metrics_sync(self):
        """Update all Prometheus metrics from current state (sync — runs in thread pool)."""
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
                SELECT AVG(t2.created_at - t1.created_at) as avg_time
                FROM (SELECT height, created_at FROM blocks ORDER BY height DESC LIMIT 101) t1
                JOIN (SELECT height, created_at FROM blocks ORDER BY height DESC LIMIT 101) t2
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
            # AI METRICS
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

            # QUSD Keeper
            if self.qusd_keeper:
                try:
                    qusd_keeper_mode.set(int(self.qusd_keeper.config.mode))
                    qusd_keeper_last_check_block.set(self.qusd_keeper._last_check_block)
                    qusd_keeper_stability_fund.set(float(self.qusd_keeper._stability_fund_qbc))
                    qusd_keeper_paused.set(1 if self.qusd_keeper._paused else 0)
                    if self.qusd_keeper._dex_reader:
                        try:
                            dev, _, _ = self.qusd_keeper._dex_reader.get_max_wqusd_deviation()
                            qusd_keeper_max_deviation.set(float(dev))
                        except Exception:
                            pass
                    if self.qusd_keeper._arb_calc:
                        try:
                            opps = self.qusd_keeper._arb_calc.get_current_opportunities(profitable_only=True)
                            qusd_keeper_arb_opportunities.set(len(opps))
                        except Exception:
                            pass
                except Exception as e:
                    logger.debug(f"Metrics update error (keeper): {e}")

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
                    try:
                        loop = asyncio.get_running_loop()
                        # Running in thread pool — schedule on the main event loop
                        asyncio.run_coroutine_threadsafe(self._update_aikgs_metrics(), loop)
                    except RuntimeError:
                        # No running loop in this thread — skip AIKGS metrics
                        pass
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

        # Start networking — Substrate bridge or P2P
        if Config.SUBSTRATE_MODE and self.substrate_bridge:
            logger.info("SUBSTRATE_MODE: Connecting to Substrate node...")
            connected = await self.substrate_bridge.connect()
            if connected:
                logger.info("Substrate bridge connected — starting block subscription")
                # Start finalized block subscription in background
                self._substrate_task = asyncio.create_task(
                    self.substrate_bridge.subscribe_finalized_blocks(
                        on_block=self._on_substrate_block_finalized
                    )
                )
            else:
                logger.error(
                    "Failed to connect to Substrate node at "
                    f"{Config.SUBSTRATE_WS_URL} — will retry in background"
                )
                self._substrate_task = asyncio.create_task(
                    self.substrate_bridge.subscribe_finalized_blocks(
                        on_block=self._on_substrate_block_finalized
                    )
                )
        elif Config.ENABLE_RUST_P2P:
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

        # Start knowledge seeder (skip in SUBSTRATE_MODE — reduces Ollama/CPU load)
        if self.knowledge_seeder and not Config.SUBSTRATE_MODE:
            # Wire knowledge graph reference for domain-weighted prompt selection
            # and internet worker direct injection
            if hasattr(self, 'aether') and self.aether and getattr(self.aether, 'kg', None):
                self.knowledge_seeder._kg = self.aether.kg
            self.knowledge_seeder.start()
            logger.info("Knowledge seeder started")
        elif Config.SUBSTRATE_MODE:
            logger.info("Knowledge seeder skipped (SUBSTRATE_MODE — Ollama reserved for blocks)")

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

        # ══════════════════════════════════════════════════════════════
        # STARTUP SYNC — MUST complete before mining gate opens.
        # A fresh node (height=-1) MUST sync from a peer before mining.
        # This prevents independent genesis blocks / chain forks.
        # ══════════════════════════════════════════════════════════════
        sync_peer = os.environ.get('SYNC_PEER_URL', Config.SYNC_PEER_URL).strip()
        local_height = self.db.get_current_height()
        sync_succeeded = False

        # ── Genesis validation: if we have blocks, verify genesis matches canonical ──
        if local_height >= 0:
            genesis_block = self.db.get_block(0)
            if genesis_block:
                genesis_hash = genesis_block.block_hash or genesis_block.calculate_hash()
                # Accept stored hash (all-zeros) or content hash as valid genesis
                valid_hashes = {Config.CANONICAL_GENESIS_HASH, Config.CANONICAL_GENESIS_CONTENT_HASH, '0' * 64}
                if genesis_hash not in valid_hashes:
                    logger.critical(
                        f"GENESIS MISMATCH: local={genesis_hash[:16]}... "
                        f"canonical={canonical[:16]}... "
                        f"This node is on an INCOMPATIBLE chain. "
                        f"Wipe the database and restart to sync from the network."
                    )
                    # Do NOT open mining gate — refuse to mine on wrong chain
                    if Config.AUTO_MINE:
                        self.mining.start()  # start thread but gate stays closed
                    logger.info("Node startup complete (MINING BLOCKED — genesis mismatch)")
                    return
                else:
                    logger.info(f"Genesis block validated: {genesis_hash[:16]}...")
                    sync_succeeded = True  # We're on the right chain

        # ── Fresh node (no blocks): MUST sync from peer ──────────────
        if local_height < 0:
            logger.info(
                f"FRESH NODE: no blocks in database (height={local_height}). "
                f"Must sync from peer before mining."
            )
            if sync_peer and hasattr(self, 'chain_sync') and self.chain_sync:
                for attempt in range(3):
                    try:
                        logger.info(f"Sync attempt {attempt+1}/3 from {sync_peer}...")
                        import httpx
                        async with httpx.AsyncClient(timeout=15) as client:
                            resp = await client.get(f"{sync_peer}/chain/info")
                            resp.raise_for_status()
                            peer_height = resp.json().get('height', 0)
                        logger.info(f"Peer at height {peer_height}, starting full sync...")
                        result = await self.chain_sync.sync_from_peer(sync_peer)
                        status = result.get('status', '')
                        if status in ('synced', 'up_to_date', 'synced_from_snapshot'):
                            sync_succeeded = True
                            local_height = self.db.get_current_height()
                            logger.info(
                                f"Startup sync SUCCESS: synced to height {local_height} "
                                f"from {sync_peer}"
                            )
                            break
                        else:
                            logger.warning(f"Sync attempt {attempt+1} result: {result}")
                    except Exception as e:
                        logger.warning(f"Sync attempt {attempt+1} failed: {e}")
                    await asyncio.sleep(5)

                if not sync_succeeded:
                    logger.error(
                        "FRESH NODE: All sync attempts failed. "
                        "Mining gate will NOT open — cannot mine without a chain. "
                        "Fix SYNC_PEER_URL and restart."
                    )
            elif not sync_peer:
                logger.error(
                    "FRESH NODE: No SYNC_PEER_URL configured. "
                    "A fresh node MUST sync from an existing peer. "
                    "Set SYNC_PEER_URL=http://<peer-ip>:5000 in .env and restart."
                )
            # Start mining thread (will be blocked by sync gate)
            if Config.AUTO_MINE:
                self.mining.start()
            if not sync_succeeded and not Config.ALLOW_GENESIS_MINE:
                logger.info("Node startup complete (MINING BLOCKED — no chain, no sync)")
                return
            elif not sync_succeeded and Config.ALLOW_GENESIS_MINE:
                logger.warning("ALLOW_GENESIS_MINE=true — mining will create canonical genesis")
                sync_succeeded = True  # Allow gate to open

        # ── Existing node: check if behind peer ──────────────────────
        elif sync_peer and hasattr(self, 'chain_sync') and self.chain_sync:
            try:
                logger.info(f"Checking sync peer {sync_peer} (local height: {local_height})...")
                import httpx
                async with httpx.AsyncClient(timeout=10) as client:
                    resp = await client.get(f"{sync_peer}/chain/info")
                    resp.raise_for_status()
                    peer_height = resp.json().get('height', 0)
                if peer_height > local_height + 1:
                    logger.info(
                        f"Peer is ahead: peer={peer_height}, local={local_height}. "
                        f"Starting chain sync before mining..."
                    )
                    if self.chain_sync.is_syncing:
                        logger.info("Waiting for in-progress P2P sync to complete...")
                        for _ in range(300):
                            await asyncio.sleep(1)
                            if not self.chain_sync.is_syncing:
                                break
                    if not self.chain_sync.is_syncing:
                        result = await self.chain_sync.sync_from_peer(sync_peer)
                        logger.info(f"Startup sync result: {result}")
                    sync_succeeded = True
                else:
                    logger.info(f"Already up to date with peer (peer={peer_height}, local={local_height})")
                    sync_succeeded = True
            except Exception as e:
                logger.warning(f"Startup sync check failed: {e}")
                # We already have blocks and validated genesis — allow mining
                sync_succeeded = True

        # Start mining (in Substrate mode, proofs are submitted as extrinsics)
        if Config.AUTO_MINE and not self.mining.is_mining:
            if Config.SUBSTRATE_MODE:
                logger.info("SUBSTRATE_MODE: Mining proofs will be submitted to Substrate")
            self.mining.start()

        # ── Open the sync gate ONLY if sync succeeded or genesis validated ──
        if sync_succeeded:
            self.mining.set_sync_complete()
            logger.info("Mining sync gate OPENED — mining enabled")
        else:
            logger.warning(
                "Mining sync gate CLOSED — sync did not succeed. "
                "Mining thread is running but blocked until sync completes."
            )

        # Snapshot check (skip in SUBSTRATE_MODE — snapshot uses Python chain heights)
        if not Config.SUBSTRATE_MODE:
            local_height = self.db.get_current_height()
            if local_height > 0 and local_height % Config.SNAPSHOT_INTERVAL == 0:
                loop = asyncio.get_event_loop()
                loop.run_in_executor(None, self.ipfs.create_snapshot, self.db, local_height)

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

        # Save AI state before shutdown
        try:
            height = self.db.get_current_height()
            self._save_agi_state(height)
        except Exception as e:
            logger.debug(f"AI state save on shutdown: {e}")

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

        # Disconnect Substrate bridge
        if self.substrate_bridge:
            await self.substrate_bridge.disconnect()
            if hasattr(self, '_substrate_task') and self._substrate_task:
                self._substrate_task.cancel()
                try:
                    await self._substrate_task
                except asyncio.CancelledError:
                    pass

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
        """Handle a block received from the Rust P2P stream.

        Fork resolution strategy (heaviest chain wins):
        - gap > 1  → we're behind, trigger chain sync
        - gap == 1 → next block, validate + store (or fork-resolve if prev_hash mismatch)
        - gap == 0 → competing block at same height, compare cumulative weight
        - gap < 0  → peer is behind us, ignore

        In all cases where a peer block at our height or next height arrives,
        the mining abort signal is fired to prevent wasting VQE cycles on a
        block that may already be obsolete.
        """
        try:
            height = block_data.get('height', 0)
            block_hash = block_data.get('hash', '')
            logger.info(f"P2P block received: height={height} hash={block_hash[:16]}...")

            blocks_received.inc()

            # Check if we're behind and need to sync
            local_height = self.db.get_current_height()
            gap = height - local_height

            if gap > 1:
                # We're behind — trigger chain sync
                logger.info(
                    f"P2P block {height} is {gap} blocks ahead of local chain "
                    f"(local={local_height}). Triggering chain sync..."
                )
                # Abort mining — we're behind, mining is wasted work
                if hasattr(self, 'mining') and self.mining:
                    self.mining.abort_current_block()
                if hasattr(self, 'chain_sync') and self.chain_sync:
                    await self.chain_sync.auto_sync_if_behind(height)
                return

            if gap < 0:
                # Peer is behind us — ignore
                logger.debug(f"P2P block {height} is behind local chain (local={local_height})")
                return

            # ── Abort mining for gap 0 and 1 — peer has a competing block ──
            if hasattr(self, 'mining') and self.mining:
                self.mining.abort_current_block()

            if gap == 1:
                # Next expected block — reconstruct, validate, and store
                from .network.chain_sync import _block_from_peer_dict
                try:
                    block = _block_from_peer_dict(block_data)
                    prev_block = self.db.get_block(local_height)

                    if prev_block:
                        expected_prev = prev_block.block_hash or prev_block.calculate_hash()
                        if block.prev_hash != expected_prev:
                            # Peer is on a different fork 1 block ahead
                            logger.warning(
                                f"P2P block {height} prev_hash mismatch — "
                                f"peer is on a different fork. Triggering fork resolution..."
                            )
                            await self._trigger_fork_resolution(height)
                            return

                    # ── Validate block before storage ──
                    valid, reason = self.consensus.validate_block(
                        block, prev_block, self.db,
                        skip_qvm=True, skip_pot=True,
                    )
                    if not valid:
                        logger.warning(
                            f"P2P block {height} failed validation: {reason}"
                        )
                        return

                    # Store the validated block (supply is tracked by
                    # chain_sync and p2p_network; no duplicate update here)
                    self.db.store_block(block)

                    current_height_metric.set(height)
                    logger.info(f"P2P block {height} stored successfully (validated)")

                    # Process for Aether knowledge
                    if self.aether:
                        try:
                            self.aether.process_block_knowledge(block)
                        except Exception:
                            pass

                except Exception as e:
                    logger.error(f"Failed to store P2P block {height}: {e}")

            elif gap == 0:
                # ── Same height — weight-based fork choice ──
                local_block = self.db.get_block(local_height)
                if local_block:
                    local_hash = local_block.block_hash or local_block.calculate_hash()
                    peer_hash = block_data.get('hash', '')
                    if peer_hash and local_hash != peer_hash:
                        # Compare cumulative weights for deterministic fork choice
                        local_weight = self.db.get_cumulative_weight(local_height)
                        peer_weight = float(block_data.get('cumulative_weight', 0))

                        if peer_weight > 0 and local_weight > 0:
                            from .consensus.engine import ConsensusEngine
                            winner = ConsensusEngine.compare_chains(
                                local_weight, local_hash, peer_weight, peer_hash,
                            )
                            if winner == "peer":
                                logger.warning(
                                    f"P2P block {height}: peer chain heavier "
                                    f"({peer_weight:.6f} vs {local_weight:.6f}). "
                                    f"Triggering fork resolution..."
                                )
                                await self._trigger_fork_resolution(height)
                            else:
                                logger.info(
                                    f"P2P block {height}: local chain heavier or tiebreak wins "
                                    f"({local_weight:.6f} vs {peer_weight:.6f}). Keeping local."
                                )
                        else:
                            # No weight data — wait for next block to resolve
                            logger.warning(
                                f"P2P block {height} at same height, different hash "
                                f"(local={local_hash[:16]}... peer={peer_hash[:16]}...). "
                                f"Waiting for next block to resolve."
                            )

        except Exception as e:
            logger.error(f"Error processing P2P block: {e}")

    async def _trigger_fork_resolution(self, peer_height: int) -> None:
        """Trigger chain sync fork resolution when we detect a fork.

        Uses ChainSync.sync_from_peer() which handles:
        1. Fork point detection via binary search
        2. Reorg validation (depth limits, checkpoints)
        3. Rollback of local chain to fork point
        4. Re-sync from peer's canonical chain
        """
        if not hasattr(self, 'chain_sync') or not self.chain_sync:
            logger.warning("Fork resolution: no chain_sync available")
            return

        if self.chain_sync._syncing:
            logger.debug("Fork resolution: sync already in progress")
            return

        # Find a peer URL to sync from
        peer_url = None
        if self.chain_sync._known_peers:
            peer_url = self.chain_sync._known_peers[0]

        if not peer_url:
            # Try to discover from SYNC_PEER_URL env var
            import os
            peer_url = os.environ.get('SYNC_PEER_URL', '').strip()

        if not peer_url:
            logger.warning(
                f"Fork resolution: detected fork at height {peer_height} but no peer URL "
                f"configured. Set SYNC_PEER_URL env var to enable automatic fork resolution."
            )
            return

        local_height = self.db.get_current_height()
        logger.info(
            f"Fork resolution: triggering sync from {peer_url} "
            f"(local={local_height}, peer={peer_height})"
        )

        # Run sync in background — sync_from_peer handles fork detection and reorg
        import asyncio
        self.chain_sync._sync_task = asyncio.create_task(
            self.chain_sync.sync_from_peer(peer_url, target_height=peer_height)
        )

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
                # Use Rust P2P — submit full block data for propagation
                success = self.rust_p2p.submit_block(
                    height=block_height,
                    block_hash=str(block_hash),
                    prev_hash=block_data.get('prev_hash', ''),
                    timestamp=int(block_data.get('timestamp', 0)),
                    difficulty=float(block_data.get('difficulty', 0)),
                    nonce=int(block_data.get('nonce', 0)),
                    miner=block_data.get('miner', ''),
                )
                if success:
                    peer_count = self.rust_p2p.get_peer_count()
                    logger.info(f"Block {block_height} broadcasted via Rust P2P to {peer_count} peers")
                else:
                    # Fallback to lightweight announcement
                    self.rust_p2p.broadcast_block(block_height, str(block_hash))
                    logger.warning(f"Full block submit failed, sent announcement for block {block_height}")
            elif self.p2p:
                # Use Python P2P for broadcasting
                asyncio.create_task(self.p2p.broadcast('block', block_data))
                peer_count = len(self.p2p.connections)
                logger.info(f"Block {block_height} broadcasted via Python P2P to {peer_count} peers")
            else:
                logger.warning("No P2P network available - block not broadcasted")

            # QUSD Keeper per-block tick
            if getattr(self, 'qusd_keeper', None) and isinstance(block_height, int):
                try:
                    self.qusd_keeper.on_block(block_height)
                except Exception as e:
                    logger.debug(f"QUSD keeper tick: {e}")

            # Periodic AI state save (every 100 blocks)
            if isinstance(block_height, int) and block_height % 100 == 0 and block_height > 0:
                try:
                    self._save_agi_state(block_height)
                except Exception as e:
                    logger.debug(f"AI state save: {e}")

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
