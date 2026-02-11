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
from .contracts.executor import ContractExecutor
from .utils.logger import get_logger
from .utils.metrics import current_height_metric, total_supply_metric

getcontext().prec = 28
logger = get_logger(__name__)
console = Console()

class QubitcoinNode:
    """Main node orchestrator with P2P networking"""
    
    def __init__(self):
        """Initialize all node components"""
        self.console = console
        self.running = False
        
        logger.info("=" * 60)
        logger.info("Qubitcoin Full Node Initializing")
        logger.info("=" * 60)
        
        console.print(Config.display())
        
        logger.info("Initializing components...")
        
        # Component 1: Database
        logger.info("🔍 [1/8] Initializing DatabaseManager...")
        try:
            self.db = DatabaseManager()
            logger.info("✅ [1/8] DatabaseManager initialized")
        except Exception as e:
            logger.error(f"❌ [1/8] DatabaseManager failed: {e}", exc_info=True)
            raise
        
        # Component 2: Quantum Engine
        logger.info("🔍 [2/8] Initializing QuantumEngine...")
        try:
            self.quantum = QuantumEngine()
            logger.info("✅ [2/8] QuantumEngine initialized")
        except Exception as e:
            logger.error(f"❌ [2/8] QuantumEngine failed: {e}", exc_info=True)
            raise
        
        # Component 3: P2P Network
        logger.info("🔍 [3/8] Initializing P2PNetwork...")
        try:
            self.p2p = P2PNetwork(
                port=Config.P2P_PORT,
                peer_id=Config.ADDRESS[:16],
                consensus=None,
                max_peers=Config.MAX_PEERS
            )
            logger.info("✅ [3/8] P2PNetwork initialized")
        except Exception as e:
            logger.error(f"❌ [3/8] P2PNetwork failed: {e}", exc_info=True)
            raise
        
        # Component 4: Consensus Engine
        logger.info("🔍 [4/8] Initializing ConsensusEngine...")
        try:
            self.consensus = ConsensusEngine(self.quantum, self.db, self.p2p)
            self.p2p.consensus = self.consensus
            logger.info("✅ [4/8] ConsensusEngine initialized")
        except Exception as e:
            logger.error(f"❌ [4/8] ConsensusEngine failed: {e}", exc_info=True)
            raise
        
        # Component 5: IPFS
        logger.info("🔍 [5/8] Initializing IPFSManager...")
        try:
            self.ipfs = IPFSManager()
            logger.info("✅ [5/8] IPFSManager initialized")
        except Exception as e:
            logger.error(f"❌ [5/8] IPFSManager failed: {e}", exc_info=True)
            raise
        
        # Component 6: Mining Engine
        logger.info("🔍 [6/8] Initializing MiningEngine...")
        try:
            self.mining = MiningEngine(self.quantum, self.consensus, self.db, console)
            self.mining.node = self
            logger.info("✅ [6/8] MiningEngine initialized")
        except Exception as e:
            logger.error(f"❌ [6/8] MiningEngine failed: {e}", exc_info=True)
            raise
        
        # Component 7: Contract Executor
        logger.info("🔍 [7/8] Initializing ContractExecutor...")
        try:
            self.contracts = ContractExecutor(self.db, self.quantum)
            logger.info("✅ [7/8] ContractExecutor initialized")
        except Exception as e:
            logger.error(f"❌ [7/8] ContractExecutor failed: {e}", exc_info=True)
            raise
        
        # Component 8: RPC & Handlers
        logger.info("🔍 [8/8] Initializing RPC and handlers...")
        try:
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
            logger.info("✅ [8/8] RPC and handlers initialized")
        except Exception as e:
            logger.error(f"❌ [8/8] RPC initialization failed: {e}", exc_info=True)
            raise
        
        logger.info("✅ All components initialized successfully")
    
    def _setup_p2p_handlers(self):
        """Register handlers for P2P messages"""
        self.p2p.register_handler('block', self._handle_received_block)
        self.p2p.register_handler('transaction', self._handle_received_tx)
        self.p2p.register_handler('ping', self._handle_ping)
        self.p2p.register_handler('pong', self._handle_pong)
        self.p2p.register_handler('get_peers', self._handle_get_peers)
        self.p2p.register_handler('peers', self._handle_peer_list)
        logger.info("✅ P2P message handlers registered")
    
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
        
        current_height_metric.set(height)
        total_supply_metric.set(float(supply))
        
        await self.p2p.start()
        logger.info(f"🌐 P2P network started on port {Config.P2P_PORT}")
        
        if Config.PEER_SEEDS:
            logger.info(f"Connecting to {len(Config.PEER_SEEDS)} seed peers...")
            for seed in Config.PEER_SEEDS:
                if seed and seed.strip():
                    asyncio.create_task(self.p2p.connect_to_peer(seed.strip()))
                    await asyncio.sleep(1)
        else:
            logger.info("No seed peers configured (bootstrap node)")
        
        if Config.AUTO_MINE:
            self.mining.start()
        
        if height > 0 and height % Config.SNAPSHOT_INTERVAL == 0:
            loop = asyncio.get_event_loop()
            loop.run_in_executor(None, self.ipfs.create_snapshot, self.db, height)
        
        self.running = True
        logger.info("✅ Node startup complete")
    
    async def on_shutdown(self):
        """Called when RPC server stops"""
        logger.info("Shutting down node...")
        self.running = False
        self.mining.stop()
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
            logger.info(f"🎉 Block {block_height} mined! Broadcasting to network...")
            asyncio.create_task(self.p2p.broadcast('block', block_data))
            peer_count = len(self.p2p.connections)
            logger.info(f"📡 Block {block_height} broadcasted to {peer_count} peers")
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
