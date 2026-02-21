"""
Qubitcoin Full Node - Main Entry Point
Coordinates all components and manages node lifecycle
"""
import asyncio
import signal
import sys
import time
from decimal import getcontext
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

        logger.info("=" * 60)
        logger.info("Qubitcoin Full Node Initializing")
        logger.info("=" * 60)

        console.print(Config.display())

        logger.info("Initializing components...")

        # Component 1: Database
        logger.info("[1/10] Initializing DatabaseManager...")
        try:
            self.db = DatabaseManager()
            logger.info("[1/10] DatabaseManager initialized")
        except Exception as e:
            logger.error(f"[1/10] DatabaseManager failed: {e}", exc_info=True)
            raise

        # Component 2: Quantum Engine
        logger.info("[2/10] Initializing QuantumEngine...")
        try:
            self.quantum = QuantumEngine()
            logger.info("[2/10] QuantumEngine initialized")
        except Exception as e:
            logger.error(f"[2/10] QuantumEngine failed: {e}", exc_info=True)
            raise

        # Component 3: P2P Network (Python or Rust)
        logger.info("[3/10] Initializing P2P Network...")
        try:
            if Config.ENABLE_RUST_P2P:
                logger.info("Using Rust P2P (libp2p 0.56)")
                self.rust_p2p = RustP2PClient(f"127.0.0.1:{Config.RUST_P2P_GRPC}")
                self.p2p = None  # Disable Python P2P
                logger.info("[3/10] Rust P2P client initialized")
            else:
                logger.info("Using Python P2P (legacy)")
                self.p2p = P2PNetwork(
                    port=Config.P2P_PORT,
                    peer_id=Config.ADDRESS[:16],
                    consensus=None,
                    max_peers=Config.MAX_PEERS
                )
                self.rust_p2p = None
                logger.info("[3/10] Python P2P initialized")
        except Exception as e:
            logger.error(f"[3/10] P2P initialization failed: {e}", exc_info=True)
            raise

        # Component 4: Consensus Engine
        logger.info("[4/10] Initializing ConsensusEngine...")
        try:
            self.consensus = ConsensusEngine(self.quantum, self.db, self.p2p)
            if self.p2p:
                self.p2p.consensus = self.consensus
            logger.info("[4/10] ConsensusEngine initialized")
        except Exception as e:
            logger.error(f"[4/10] ConsensusEngine failed: {e}", exc_info=True)
            raise

        # Component 5: IPFS
        logger.info("[5/10] Initializing IPFSManager...")
        try:
            self.ipfs = IPFSManager()
            logger.info("[5/10] IPFSManager initialized")
        except Exception as e:
            logger.error(f"[5/10] IPFSManager failed: {e}", exc_info=True)
            raise

        # Component 6: QVM State Manager (bytecode VM + state roots)
        logger.info("[6/10] Initializing QVM StateManager...")
        try:
            self.state_manager = StateManager(self.db, self.quantum)
            self.consensus.state_manager = self.state_manager
            logger.info("[6/10] QVM StateManager initialized (155 opcodes, 10 quantum)")
        except Exception as e:
            logger.error(f"[6/10] QVM StateManager failed: {e}", exc_info=True)
            raise

        # Component 7: Aether Tree (AGI layer)
        logger.info("[7/10] Initializing Aether Engine...")
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
                    genesis_hash = genesis_block.hash if genesis_block else '0' * 64
                    genesis_ts = genesis_block.timestamp if genesis_block else None
                    result = self.aether_genesis.initialize_genesis(genesis_hash, genesis_ts)
                    logger.info(
                        f"Aether genesis initialized: "
                        f"{result['knowledge_nodes_created']} nodes seeded"
                    )
                except Exception as e:
                    logger.debug(f"Aether genesis init skipped (DB not ready): {e}")

            logger.info("[7/10] Aether Engine initialized (KnowledgeGraph + Phi + Reasoning + PoT)")
        except Exception as e:
            logger.error(f"[7/10] Aether Engine failed: {e}", exc_info=True)
            raise

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

        # Component 8: Mining Engine
        logger.info("[8/10] Initializing MiningEngine...")
        try:
            self.mining = MiningEngine(self.quantum, self.consensus, self.db, console,
                                       state_manager=self.state_manager,
                                       aether_engine=self.aether)
            self.mining.node = self
            logger.info("[8/10] MiningEngine initialized")
        except Exception as e:
            logger.error(f"[8/10] MiningEngine failed: {e}", exc_info=True)
            raise

        # Component 9: Contract Executor (legacy template contracts)
        logger.info("[9/10] Initializing ContractExecutor...")
        try:
            self.contracts = ContractExecutor(self.db, self.quantum)
            logger.info("[9/10] ContractExecutor initialized")
        except Exception as e:
            logger.error(f"[9/10] ContractExecutor failed: {e}", exc_info=True)
            raise

        # Component 10: RPC & Handlers
        logger.info("[10/10] Initializing RPC and handlers...")
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
            )
            self.app.node = self
            self.app.on_event("startup")(self.on_startup)
            self.app.on_event("shutdown")(self.on_shutdown)

            # Wire RPC-created trackers back into engines so they receive data
            if self.aether and hasattr(self.app, 'consciousness_dashboard'):
                self.aether.consciousness_dashboard = self.app.consciousness_dashboard
            if hasattr(self.app, 'circulation_tracker'):
                self.mining.circulation_tracker = self.app.circulation_tracker

            logger.info("[10/10] RPC and handlers initialized")
        except Exception as e:
            logger.error(f"[10/10] RPC initialization failed: {e}", exc_info=True)
            raise

        logger.info("All 10 components initialized successfully")

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
            current_difficulty_metric.set(
                self.mining.stats.get('current_difficulty', Config.INITIAL_DIFFICULTY)
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
            contract_stats = self.db.query_one("""
                SELECT
                    COUNT(*) as total,
                    COUNT(*) FILTER (WHERE is_active = true) as active_count
                FROM contracts
            """)
            if contract_stats:
                total_contracts.set(contract_stats.get('total', 0))
                active_contracts.set(contract_stats.get('active_count', 0))

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

        if self.rust_p2p:
            self.rust_p2p.disconnect()
        if self.p2p:
            await self.p2p.stop()

        console.print(Panel.fit(
            "[bold yellow]Qubitcoin Node Stopped[/]",
            border_style="yellow"
        ))
        logger.info("Node shutdown complete")

    def on_block_mined(self, block_data: dict):
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

        except Exception as e:
            logger.error(f"Error broadcasting mined block: {e}")

    def run(self):
        """Run the node"""
        import uvicorn

        def signal_handler(signum, frame):
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

def main():
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
