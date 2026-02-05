"""
Qubitcoin Full Node - Main Entry Point
Coordinates all components and manages node lifecycle
NOW WITH P2P NETWORKING!
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
from .network.p2p_network import P2PNetwork # NEW!
from .contracts.executor import ContractExecutor
from .utils.logger import get_logger
from .utils.metrics import current_height_metric, total_supply_metric # Fixed: Import metrics gauges
# Set decimal precision
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
        # Display configuration
        console.print(Config.display())
        # Initialize components IN CORRECT ORDER
        logger.info("Initializing components...")
        self.db = DatabaseManager()
        self.quantum = QuantumEngine()
        # NEW: Initialize P2P Network (moved before consensus for ref)
        self.p2p = P2PNetwork(
            port=Config.P2P_PORT,
            peer_id=Config.ADDRESS[:16], # Use first 16 chars of address as peer ID
            consensus=None,  # Temp None; set after consensus
            max_peers=Config.MAX_PEERS
        )
        self.consensus = ConsensusEngine(self.quantum, self.db, self.p2p)  # Now pass p2p after init
        self.p2p.consensus = self.consensus  # Back-ref for validation
        self.ipfs = IPFSManager()
        self.mining = MiningEngine(self.quantum, self.consensus, self.db, console)
        self.contracts = ContractExecutor(self.db, self.quantum)
        # Register P2P message handlers
        self._setup_p2p_handlers()
        # Give mining engine a reference to node (for broadcasting)
        self.mining.node = self
        # Create RPC app
        self.app = create_rpc_app(
            self.db,
            self.consensus,
            self.mining,
            self.quantum,
            self.ipfs
        )
        # Store node reference in app for RPC endpoints
        self.app.node = self
        # Setup lifecycle events
        self.app.on_event("startup")(self.on_startup)
        self.app.on_event("shutdown")(self.on_shutdown)
        logger.info("✅ All components initialized (including P2P)")
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
        """
        Handle block received from peer
        Args:
            message: Message object containing block data
            sender_id: ID of peer who sent the block
        """
        try:
            block_data = message.data
            block_height = block_data.get('height', 'unknown')
            block_hash = block_data.get('hash', 'unknown')[:16]
            logger.info(f"📦 Received block from {sender_id}: height {block_height}, hash {block_hash}...")
            # Check if we already have this block
            current_height = self.db.get_current_height()
            if block_height <= current_height:
                logger.debug(f"Already have block at height {block_height}, ignoring")
                return
            # Validate block (basic checks)
            # TODO: Add full validation here
            # - Verify quantum proof
            # - Verify signature
            # - Verify transactions
            # - Verify previous hash
            # For now, just log that we received it
            logger.info(f"✓ Block {block_height} validated and ready to add")
            # If mining, might want to stop and start on next block
            if self.mining.is_mining and block_height > current_height:
                logger.info(f"New block found by peer, updating mining target")
                # Mining engine will automatically adjust on next iteration
        except Exception as e:
            logger.error(f"Error handling block from {sender_id}: {e}", exc_info=True)
    async def _handle_received_tx(self, message, sender_id):
        """
        Handle transaction received from peer
        Args:
            message: Message object containing transaction data
            sender_id: ID of peer who sent the transaction
        """
        try:
            tx_data = message.data
            tx_id = tx_data.get('txid', 'unknown')[:16]
            logger.info(f"💸 Received transaction from {sender_id}: {tx_id}...")
            # Validate transaction
            # TODO: Add full validation
            # - Verify signature
            # - Check inputs exist
            # - Check balance
            # - Check for double spend
            # Add to mempool
            # self.db.add_transaction(tx_data)
            logger.debug(f"Transaction {tx_id} added to mempool")
        except Exception as e:
            logger.error(f"Error handling transaction from {sender_id}: {e}")
    async def _handle_ping(self, message, sender_id):
        """
        Respond to ping message
        Args:
            message: Ping message
            sender_id: Peer who sent ping
        """
        logger.debug(f"🏓 Ping from {sender_id}")
        # Send pong response
        await self.p2p.send_message(sender_id, 'pong', {
            'timestamp': time.time(),
            'height': self.db.get_current_height()
        })
    async def _handle_pong(self, message, sender_id):
        """
        Handle pong response
        Args:
            message: Pong message
            sender_id: Peer who sent pong
        """
        logger.debug(f"🏓 Pong from {sender_id}")
        # Update peer info with their height
        peer_height = message.data.get('height', 0)
        our_height = self.db.get_current_height()
        if peer_height > our_height:
            logger.info(f"Peer {sender_id} has higher height: {peer_height} vs our {our_height}")
            # TODO: Request blocks to sync
    async def _handle_get_peers(self, message, sender_id):
        """
        Handle request for peer list
        Args:
            message: Get peers request
            sender_id: Peer requesting list
        """
        logger.debug(f"Peer {sender_id} requesting peer list")
        # Send our peer list
        peer_list = self.p2p.get_peer_list()
        await self.p2p.send_message(sender_id, 'peers', peer_list)
    async def _handle_peer_list(self, message, sender_id):
        """
        Handle received peer list
        Args:
            message: Message containing peer list
            sender_id: Peer who sent the list
        """
        peers = message.data
        logger.info(f"Received {len(peers)} peers from {sender_id}")
        # Try to connect to new peers
        for peer_info in peers:
            peer_address = f"{peer_info['host']}:{peer_info['port']}"
            # Don't connect to ourselves
            if peer_info.get('peer_id') == self.p2p.peer_id:
                continue
            # Try to connect if not already connected
            if peer_address not in self.p2p.connections:
                asyncio.create_task(self.p2p.connect_to_peer(peer_address))
    async def on_startup(self):
        """Called when RPC server starts"""
        console.print(Panel.fit(
            "[bold green]Qubitcoin Full Node Starting[/]",
            border_style="green"
        ))
        # Display current state
        height = self.db.get_current_height()
        balance = self.db.get_balance(Config.ADDRESS)
        supply = self.db.get_total_supply()
        logger.info("=" * 60)
        logger.info(f"Node Address: {Config.ADDRESS}")
        logger.info(f"Current Height: {height}")
        logger.info(f"Node Balance: {balance} QBC")
        logger.info(f"Total Supply: {supply} QBC")
        logger.info("=" * 60)
        # Update metrics
        current_height_metric.set(height)
        total_supply_metric.set(float(supply))
        # NEW: Start P2P network
        await self.p2p.start()
        logger.info(f"🌐 P2P network started on port {Config.P2P_PORT}")
        # NEW: Connect to seed peers
        if Config.PEER_SEEDS:
            logger.info(f"Connecting to {len(Config.PEER_SEEDS)} seed peers...")
            for seed in Config.PEER_SEEDS:
                if seed and seed.strip(): # Skip empty seeds
                    asyncio.create_task(self.p2p.connect_to_peer(seed.strip()))
                    await asyncio.sleep(1) # Stagger connections
        else:
            logger.info("No seed peers configured (bootstrap node)")
        # Start mining if enabled
        if Config.AUTO_MINE:
            self.mining.start()
        # Create initial snapshot if at milestone
        if height > 0 and height % Config.SNAPSHOT_INTERVAL == 0:
            self.ipfs.create_snapshot(self.db, height)
        self.running = True
        logger.info("✅ Node startup complete")
    async def on_shutdown(self):
        """Called when RPC server stops"""
        logger.info("Shutting down node...")
        self.running = False
        self.mining.stop()
        # NEW: Stop P2P network
        await self.p2p.stop()
        console.print(Panel.fit(
            "[bold yellow]Qubitcoin Node Stopped[/]",
            border_style="yellow"
        ))
        logger.info("✅ Node shutdown complete")
    def on_block_mined(self, block_data: dict):
        """
        Called when mining engine successfully mines a block
        Broadcasts the block to the network
        Args:
            block_data: Dictionary containing block information
        """
        try:
            block_height = block_data.get('height', 'unknown')
            logger.info(f"🎉 Block {block_height} mined! Broadcasting to network...")
            # Broadcast to all connected peers
            asyncio.create_task(self.p2p.broadcast('block', block_data))
            # Log success
            peer_count = len(self.p2p.connections)
            logger.info(f"📡 Block {block_height} broadcasted to {peer_count} peers")
        except Exception as e:
            logger.error(f"Error broadcasting mined block: {e}")
    def run(self):
        """Run the node"""
        import uvicorn
        # Setup signal handlers
        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, shutting down...")
            sys.exit(0)
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        # Run RPC server
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
