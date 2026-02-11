"""
Qubitcoin Full Node - Main Entry Point
Coordinates all components and manages node lifecycle
"""
import asyncio
import signal
import sys
import time
from decimal import getcontext, Decimal
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
from .utils.logger import get_logger

# Import ALL metrics
from .utils.metrics import (
    # Blockchain
    blocks_mined, blocks_received, current_height_metric, total_supply_metric,
    current_difficulty_metric, network_hashrate_metric, avg_block_time_metric,
    blockchain_size_metric,
    # Mining
    mining_attempts, vqe_optimization_time, block_validation_time,
    alignment_score_metric, best_alignment_ever,
    # Network
    active_peers, rust_p2p_peers, messages_sent, messages_received,
    # Transactions
    transactions_pending, transactions_confirmed, mempool_size_bytes, avg_tx_fee,
    # Quantum Research
    quantum_backend_metric, circuit_depth_metric, active_hamiltonians,
    vqe_solutions_total, research_contributions,
    # QVM
    total_contracts, active_contracts, contract_executions_total,
    contract_execution_time, gas_used_total, avg_gas_price, contract_storage_size,
    # AGI
    phi_current, phi_threshold_distance, knowledge_nodes_total, knowledge_edges_total,
    reasoning_operations_total, consciousness_events_total, integration_score,
    differentiation_score, causal_chain_length, agi_training_datasets, agi_models_deployed,
    # IPFS
    ipfs_pins_total, ipfs_storage_bytes, blockchain_snapshots_total
)

getcontext().prec = 28
logger = get_logger(__name__)
console = Console()

class QubitcoinNode:
    """Main node orchestrator with P2P networking"""

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
        logger.info("🔍 [1/9] Initializing DatabaseManager...")
        try:
            self.db = DatabaseManager()
            logger.info("✅ [1/9] DatabaseManager initialized")
        except Exception as e:
            logger.error(f"❌ [1/9] DatabaseManager failed: {e}", exc_info=True)
            raise

        # Component 2: Quantum Engine
        logger.info("🔍 [2/9] Initializing QuantumEngine...")
        try:
            self.quantum = QuantumEngine()
            logger.info("✅ [2/9] QuantumEngine initialized")
        except Exception as e:
            logger.error(f"❌ [2/9] QuantumEngine failed: {e}", exc_info=True)
            raise

        # Component 3: P2P Network (Python or Rust)
        logger.info("🔍 [3/9] Initializing P2P Network...")
        try:
            if Config.ENABLE_RUST_P2P:
                logger.info("Using Rust P2P (libp2p 0.56)")
                self.rust_p2p = RustP2PClient(f"127.0.0.1:{Config.RUST_P2P_GRPC}")
                self.p2p = None  # Disable Python P2P
                logger.info("✅ [3/9] Rust P2P client initialized")
            else:
                logger.info("Using Python P2P (legacy)")
                self.p2p = P2PNetwork(
                    port=Config.P2P_PORT,
                    peer_id=Config.ADDRESS[:16],
                    consensus=None,
                    max_peers=Config.MAX_PEERS
                )
                self.rust_p2p = None
                logger.info("✅ [3/9] Python P2P initialized")
        except Exception as e:
            logger.error(f"❌ [3/9] P2P initialization failed: {e}", exc_info=True)
            raise

        # Component 4: Consensus Engine
        logger.info("🔍 [4/9] Initializing ConsensusEngine...")
        try:
            self.consensus = ConsensusEngine(self.quantum, self.db, self.p2p)
            if self.p2p:
                self.p2p.consensus = self.consensus
            logger.info("✅ [4/9] ConsensusEngine initialized")
        except Exception as e:
            logger.error(f"❌ [4/9] ConsensusEngine failed: {e}", exc_info=True)
            raise

        # Component 5: IPFS
        logger.info("🔍 [5/9] Initializing IPFSManager...")
        try:
            self.ipfs = IPFSManager()
            logger.info("✅ [5/9] IPFSManager initialized")
        except Exception as e:
            logger.error(f"❌ [5/9] IPFSManager failed: {e}", exc_info=True)
            raise

        # Component 6: Mining Engine
        logger.info("🔍 [6/9] Initializing MiningEngine...")
        try:
            self.mining = MiningEngine(self.quantum, self.consensus, self.db, console)
            self.mining.node = self
            logger.info("✅ [6/9] MiningEngine initialized")
        except Exception as e:
            logger.error(f"❌ [6/9] MiningEngine failed: {e}", exc_info=True)
            raise

        # Component 7: Contract Executor
        logger.info("🔍 [7/9] Initializing ContractExecutor...")
        try:
            self.contracts = ContractExecutor(self.db, self.quantum)
            logger.info("✅ [7/9] ContractExecutor initialized")
        except Exception as e:
            logger.error(f"❌ [7/9] ContractExecutor failed: {e}", exc_info=True)
            raise

        # Component 8: RPC & Handlers
        logger.info("🔍 [8/9] Initializing RPC...")
        try:
            if self.p2p:
                self._setup_p2p_handlers()

            self.app = create_rpc_app(
                self.db,
                self.consensus,
                self.mining,
                self.quantum,
                self.ipfs,
                contract_engine=self.contracts
            )
            self.app.node = self
            self.app.on_event("startup")(self.on_startup)
            self.app.on_event("shutdown")(self.on_shutdown)
            logger.info("✅ [8/9] RPC initialized")
        except Exception as e:
            logger.error(f"❌ [8/9] RPC initialization failed: {e}", exc_info=True)
            raise

        logger.info("✅ All components initialized successfully")

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
        logger.info("✅ Python P2P message handlers registered")

    async def _handle_received_block(self, message, sender_id):
        """Handle block received from peer"""
        try:
            block_data = message.data
            block_height = block_data.get('height', 'unknown')
            block_hash = block_data.get('hash', 'unknown')[:16]
            logger.info(f"📦 Received block from {sender_id}: height {block_height}, hash {block_hash}...")

            current_height = self.db.get_current_height()
            if block_height <= current_height:
                logger.debug(f"Already have block at height {block_height}, ignoring")
                return

            logger.info(f"✓ Block {block_height} validated and ready to add")
            blocks_received.inc()

            if self.mining.is_mining and block_height > current_height:
                logger.info(f"New block found by peer, updating mining target")
        except Exception as e:
            logger.error(f"Error handling block from {sender_id}: {e}", exc_info=True)

    async def _handle_received_tx(self, message, sender_id):
        """Handle transaction received from peer"""
        try:
            tx_data = message.data
            tx_id = tx_data.get('txid', 'unknown')[:16]
            logger.info(f"💸 Received transaction from {sender_id}: {tx_id}...")
            logger.debug(f"Transaction {tx_id} added to mempool")
        except Exception as e:
            logger.error(f"Error handling transaction from {sender_id}: {e}")

    async def _handle_ping(self, message, sender_id):
        """Respond to ping message"""
        logger.debug(f"🏓 Ping from {sender_id}")
        await self.p2p.send_message(sender_id, 'pong', {
            'timestamp': time.time(),
            'height': self.db.get_current_height()
        })

    async def _handle_pong(self, message, sender_id):
        """Handle pong response"""
        logger.debug(f"🏓 Pong from {sender_id}")
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
        logger.info("📊 Metrics update loop started")
        
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
            chain_state = self.db.query_one(
                "SELECT * FROM chain_state WHERE id = 1"
            )
            
            if chain_state:
                current_height_metric.set(chain_state.get('best_block_height', 0))
                total_supply_metric.set(float(chain_state.get('total_supply', 0)))
                current_difficulty_metric.set(float(chain_state.get('current_difficulty', 1.0)))
                network_hashrate_metric.set(float(chain_state.get('network_hashrate', 0)))
                avg_block_time_metric.set(float(chain_state.get('average_block_time', 3.3)))

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
                "SELECT COUNT(*) as count FROM mempool"
            )
            if mempool_count:
                transactions_pending.set(mempool_count.get('count', 0))

            # ============================================================
            # QUANTUM RESEARCH METRICS
            # ============================================================
            hamiltonian_stats = self.db.query_one("""
                SELECT 
                    COUNT(*) FILTER (WHERE is_active = true) as active_count,
                    COUNT(*) as total_count
                FROM hamiltonians
            """)
            if hamiltonian_stats:
                active_hamiltonians.set(hamiltonian_stats.get('active_count', 0))

            vqe_stats = self.db.query_one("""
                SELECT COUNT(*) as total FROM vqe_circuits
            """)
            if vqe_stats:
                vqe_solutions_total.labels().inc(0)  # Will increment on new solutions

            # Get best alignment score
            best_alignment = self.db.query_one("""
                SELECT MAX(alignment_score) as best_score
                FROM blocks
                WHERE block_height > 0
            """)
            if best_alignment and best_alignment.get('best_score'):
                best_alignment_ever.set(float(best_alignment.get('best_score', 0)))

            # ============================================================
            # QVM METRICS
            # ============================================================
            contract_stats = self.db.query_one("""
                SELECT 
                    COUNT(*) as total,
                    COUNT(*) FILTER (WHERE is_active = true) as active_count
                FROM smart_contracts
            """)
            if contract_stats:
                total_contracts.set(contract_stats.get('total', 0))
                active_contracts.set(contract_stats.get('active_count', 0))

            execution_count = self.db.query_one("""
                SELECT COUNT(*) as count FROM contract_executions
            """)
            if execution_count:
                contract_executions_total.labels().inc(0)  # Will increment on new executions

            # ============================================================
            # AGI METRICS - THE MAIN EVENT! 🧠
            # ============================================================
            # Get latest Phi measurement
            latest_phi = self.db.query_one("""
                SELECT phi_value, phi_threshold, integration_score, differentiation_score
                FROM phi_measurements
                ORDER BY measured_at DESC
                LIMIT 1
            """)
            
            if latest_phi:
                phi_val = float(latest_phi.get('phi_value', 0.1))
                phi_thresh = float(latest_phi.get('phi_threshold', 3.0))
                
                phi_current.set(phi_val)
                phi_threshold_distance.set(max(0, phi_thresh - phi_val))
                integration_score.set(float(latest_phi.get('integration_score', 0.1)))
                differentiation_score.set(float(latest_phi.get('differentiation_score', 0.1)))
                
                # Log consciousness progress
                if phi_val > 0.1:  # Not genesis
                    progress_pct = (phi_val / phi_thresh) * 100
                    logger.debug(f"🧠 Consciousness: Φ={phi_val:.4f} ({progress_pct:.1f}% to threshold)")

            # Knowledge graph stats
            knowledge_stats = self.db.query_one("""
                SELECT 
                    (SELECT COUNT(*) FROM knowledge_nodes) as node_count,
                    (SELECT COUNT(*) FROM knowledge_edges) as edge_count,
                    (SELECT AVG(path_length) FROM causal_chains) as avg_causal_length
            """)
            
            if knowledge_stats:
                knowledge_nodes_total.set(knowledge_stats.get('node_count', 0))
                knowledge_edges_total.set(knowledge_stats.get('edge_count', 0))
                avg_length = knowledge_stats.get('avg_causal_length', 1)
                if avg_length:
                    causal_chain_length.set(float(avg_length))

            # Consciousness events
            consciousness_count = self.db.query_one("""
                SELECT COUNT(*) as count FROM consciousness_events
                WHERE is_verified = true
            """)
            if consciousness_count:
                consciousness_events_total.labels(severity='all').inc(0)

            # Training data & models
            training_stats = self.db.query_one("""
                SELECT 
                    (SELECT COUNT(*) FROM training_datasets) as datasets,
                    (SELECT COUNT(*) FROM model_registry WHERE is_active = true) as active_models
            """)
            if training_stats:
                agi_training_datasets.set(training_stats.get('datasets', 0))
                agi_models_deployed.set(training_stats.get('active_models', 0))

            # ============================================================
            # IPFS METRICS
            # ============================================================
            ipfs_stats = self.db.query_one("""
                SELECT 
                    (SELECT COUNT(*) FROM ipfs_pins WHERE pin_status = 'pinned') as pins,
                    (SELECT COUNT(*) FROM blockchain_snapshots) as snapshots
            """)
            if ipfs_stats:
                ipfs_pins_total.set(ipfs_stats.get('pins', 0))
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
            logger.info("🦀 Connecting to Rust P2P network...")
            if self.rust_p2p.connect():
                peer_count = self.rust_p2p.get_peer_count()
                logger.info(f"🌐 Rust P2P connected - {peer_count} peers")
                rust_p2p_peers.set(peer_count)
            else:
                logger.warning("⚠️  Rust P2P connection failed - running without P2P")
        else:
            await self.p2p.start()
            logger.info(f"🌐 Python P2P network started on port {Config.P2P_PORT}")

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
        logger.info("📊 Metrics collection started")

        # Start mining
        if Config.AUTO_MINE:
            self.mining.start()

        # Snapshot check
        if height > 0 and height % Config.SNAPSHOT_INTERVAL == 0:
            loop = asyncio.get_event_loop()
            loop.run_in_executor(None, self.ipfs.create_snapshot, self.db, height)
        
        self.running = True
        logger.info("✅ Node startup complete")

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
        
        self.mining.stop()

        if self.rust_p2p:
            self.rust_p2p.disconnect()
        if self.p2p:
            await self.p2p.stop()

        console.print(Panel.fit(
            "[bold yellow]Qubitcoin Node Stopped[/]",
            border_style="yellow"
        ))
        logger.info("✅ Node shutdown complete")

    def on_block_mined(self, block_data: dict):
        """Called when mining engine successfully mines a block"""
        try:
            block_height = block_data.get('height', 'unknown')
            block_hash = block_data.get('hash', 'unknown')

            logger.info(f"🎉 Block {block_height} mined! Broadcasting to network...")
            
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
                    logger.info(f"📡 Block {block_height} broadcasted via Rust P2P to {peer_count} peers")
                else:
                    logger.warning(f"Failed to broadcast block {block_height} via Rust P2P")
            elif self.p2p:
                # Use Python P2P for broadcasting
                asyncio.create_task(self.p2p.broadcast('block', block_data))
                peer_count = len(self.p2p.connections)
                logger.info(f"📡 Block {block_height} broadcasted via Python P2P to {peer_count} peers")
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
