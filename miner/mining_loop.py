"""
Mining Loop — orchestrates the VQE mining cycle.

Flow:
1. Connect to Substrate node via WebSocket
2. Subscribe to finalized block headers
3. For each new finalized block:
   a. Extract parent_hash and compute target_height
   b. Query current difficulty from on-chain storage
   c. Run VQE optimization against the deterministic Hamiltonian
   d. If energy < difficulty_threshold: submit proof on-chain
4. Repeat until interrupted

This is the "main loop" equivalent of Bitcoin's mining loop, but instead of
incrementing a nonce, we run VQE optimization with random initial parameters.
"""

import logging
import signal
import time
from typing import Optional

from .config import MinerConfig
from .substrate_client import SubstrateClient
from .vqe_miner import VqeMiner

logger = logging.getLogger("qubitcoin.miner")


class MiningLoop:
    """Orchestrates the VQE mining cycle against the Substrate node."""

    def __init__(self) -> None:
        self.running: bool = False
        self.client: Optional[SubstrateClient] = None
        self.miner: Optional[VqeMiner] = None
        self.blocks_attempted: int = 0
        self.blocks_mined: int = 0

    def start(self) -> None:
        """Initialize components and start the mining loop."""
        logger.info("=" * 60)
        logger.info("  Qubitcoin VQE Mining Client")
        logger.info("=" * 60)

        # Initialize VQE miner (quantum backend)
        self.miner = VqeMiner()
        logger.info(f"Backend: {self.miner.backend_name}")
        logger.info(f"Qubits: {MinerConfig.NUM_QUBITS}")
        logger.info(f"VQE reps: {MinerConfig.VQE_REPS}")
        logger.info(f"Max iterations: {MinerConfig.VQE_MAXITER}")
        logger.info(f"Max attempts/block: {MinerConfig.MAX_MINING_ATTEMPTS}")

        # Connect to Substrate node
        self.client = SubstrateClient()
        logger.info(f"Node: {MinerConfig.SUBSTRATE_WS_URL}")
        logger.info(f"Miner: {self.client.keypair.ss58_address}")

        # Register signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._handle_shutdown)
        signal.signal(signal.SIGTERM, self._handle_shutdown)

        self.running = True
        logger.info("")
        logger.info("Mining started. Waiting for finalized blocks...")
        logger.info("")

        self._mine_loop()

    def _mine_loop(self) -> None:
        """
        Main mining loop — subscribe to finalized heads and mine each one.

        CRITICAL: We mine against finalized blocks (not best blocks) because:
        1. GRANDPA finality guarantees the parent won't be reverted
        2. The Hamiltonian seed depends on parent_hash — if parent changes, seed changes
        3. Mining against unfinalized blocks wastes compute on potentially-orphaned chains
        """
        for header in self.client.subscribe_finalized_heads():
            if not self.running:
                break

            block_number = int(header["header"]["number"], 16)
            parent_hash_hex = header["header"]["parentHash"]

            # Target height = finalized height + 1
            # We're mining the NEXT block after this finalized one
            target_height = block_number + 1

            # Convert parent hash to raw bytes (strip 0x prefix)
            # NOTE: For mining the next block, we need the HASH OF THE
            # FINALIZED BLOCK (not its parent hash). The finalized block's
            # hash IS the parent hash of the block we're mining.
            finalized_hash = header.get("hash")
            if finalized_hash:
                parent_hash = bytes.fromhex(finalized_hash.lstrip("0x"))
            else:
                # Fallback: compute from block hash query
                block_hash = self.client.get_block_hash(block_number)
                if block_hash:
                    parent_hash = bytes.fromhex(block_hash.lstrip("0x"))
                else:
                    logger.error(
                        f"Cannot determine hash for finalized block {block_number}"
                    )
                    continue

            # Query current difficulty from on-chain storage
            difficulty = self.client.get_current_difficulty()

            self.blocks_attempted += 1

            logger.info(
                f"New target: block {target_height} | "
                f"difficulty={difficulty} | "
                f"parent={parent_hash[:8].hex()}..."
            )

            # Run VQE mining
            start = time.monotonic()
            result = self.miner.mine_block(parent_hash, target_height, difficulty)
            elapsed = time.monotonic() - start

            if result is None:
                logger.info(
                    f"No solution found for block {target_height} "
                    f"({elapsed:.1f}s). Waiting for next block..."
                )
                continue

            # Submit proof to Substrate
            logger.info(
                f"Submitting proof: energy_scaled={result['energy_scaled']}, "
                f"attempt={result['attempt']}, time={elapsed:.1f}s"
            )

            tx_hash = self.client.submit_mining_proof(
                vqe_params=result["params_scaled"],
                energy=result["energy_scaled"],
                hamiltonian_seed=result["hamiltonian_seed"],
                n_qubits=result["n_qubits"],
            )

            if tx_hash:
                self.blocks_mined += 1
                logger.info(
                    f"BLOCK {target_height} MINED! "
                    f"tx={tx_hash[:18]}... "
                    f"({self.blocks_mined}/{self.blocks_attempted} success rate)"
                )
            else:
                logger.warning(
                    f"Proof rejected for block {target_height}. "
                    f"May have been mined by another miner."
                )

    def _handle_shutdown(self, signum: int, frame: object) -> None:
        """Handle SIGINT/SIGTERM for graceful shutdown."""
        logger.info("")
        logger.info("Shutdown signal received. Stopping mining...")
        self.running = False

    def stop(self) -> None:
        """Stop the mining loop and close connections."""
        self.running = False
        if self.client:
            self.client.close()
        logger.info(
            f"Mining stopped. "
            f"Blocks attempted: {self.blocks_attempted}, "
            f"Blocks mined: {self.blocks_mined}"
        )
