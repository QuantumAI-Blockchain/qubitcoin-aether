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
from .contracts.executor import ContractExecutor
from .utils.logger import get_logger
from .utils.metrics import current_height_metric, total_supply_metric

# Set decimal precision
getcontext().prec = 28

logger = get_logger(__name__)
console = Console()


class QubitcoinNode:
    """Main node orchestrator"""

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
        self.consensus = ConsensusEngine(self.quantum)
        self.ipfs = IPFSManager()
        self.mining = MiningEngine(self.quantum, self.consensus, self.db, console)
        self.contracts = ContractExecutor(self.db, self.quantum)

        # Create RPC app
        self.app = create_rpc_app(
            self.db,
            self.consensus,
            self.mining,
            self.quantum,
            self.ipfs
        )

        # Setup lifecycle events
        self.app.on_event("startup")(self.on_startup)
        self.app.on_event("shutdown")(self.on_shutdown)

        logger.info("✅ All components initialized")

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

        console.print(Panel.fit(
            "[bold yellow]Qubitcoin Node Stopped[/]",
            border_style="yellow"
        ))

        logger.info("✅ Node shutdown complete")

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
