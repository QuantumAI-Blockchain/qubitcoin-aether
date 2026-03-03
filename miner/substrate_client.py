"""
Substrate RPC Client — WebSocket connection to the QBC Substrate node.

Handles:
- Subscribing to finalized block headers (new mining targets)
- Querying on-chain storage (difficulty, block height)
- Submitting signed extrinsics (submit_mining_proof)

Uses `substrate-interface` — the standard Python Substrate client library.
"""

import logging
import time
from typing import Optional, Generator, Any, Dict

from substrateinterface import SubstrateInterface, Keypair
from substrateinterface.exceptions import SubstrateRequestException

from .config import MinerConfig

logger = logging.getLogger("qubitcoin.miner")


class SubstrateClient:
    """WebSocket RPC client for the QBC Substrate node."""

    def __init__(self) -> None:
        self.substrate: Optional[SubstrateInterface] = None
        self.keypair: Optional[Keypair] = None
        self._connect()

    def _connect(self) -> None:
        """Establish WebSocket connection and load miner keypair."""
        logger.info(f"Connecting to Substrate node: {MinerConfig.SUBSTRATE_WS_URL}")

        self.substrate = SubstrateInterface(
            url=MinerConfig.SUBSTRATE_WS_URL,
            ss58_format=88,  # QBC custom prefix
            type_registry_preset="default",
        )

        # Load miner keypair from seed phrase or dev account URI
        seed = MinerConfig.MINER_SEED
        if seed.startswith("//"):
            # Dev account (e.g., //Alice, //Bob)
            self.keypair = Keypair.create_from_uri(seed)
        else:
            # Mnemonic seed phrase
            self.keypair = Keypair.create_from_mnemonic(seed)

        logger.info(
            f"Miner address: {self.keypair.ss58_address} "
            f"(SS58 prefix 88)"
        )

    def reconnect(self) -> None:
        """Reconnect to the Substrate node after a connection loss."""
        logger.warning("Reconnecting to Substrate node...")
        try:
            if self.substrate:
                self.substrate.close()
        except Exception:
            pass
        self._connect()

    def get_current_difficulty(self) -> int:
        """
        Query CurrentDifficulty from the qbc-consensus pallet.

        Returns:
            Difficulty as u64 (scaled by 10^6; 1_000_000 = difficulty 1.0)
        """
        result = self.substrate.query(
            module="QbcConsensus",
            storage_function="CurrentDifficulty",
        )
        return int(result.value)

    def get_block_height(self) -> int:
        """
        Query current block height from the qbc-utxo pallet.

        Returns:
            Current block height as u64.
        """
        result = self.substrate.query(
            module="QbcUtxo",
            storage_function="CurrentHeight",
        )
        return int(result.value)

    def get_finalized_head(self) -> str:
        """Get the hash of the latest finalized block."""
        return self.substrate.get_chain_finalised_head()

    def get_block_hash(self, block_number: int) -> Optional[str]:
        """Get block hash by number."""
        return self.substrate.get_block_hash(block_number)

    def get_block_header(self, block_hash: str) -> Dict[str, Any]:
        """
        Get block header by hash.

        Returns:
            Dict with: number, parentHash, stateRoot, extrinsicsRoot
        """
        return self.substrate.get_block_header(block_hash)

    def subscribe_finalized_heads(self) -> Generator[Dict[str, Any], None, None]:
        """
        Subscribe to finalized block headers via WebSocket.

        Yields block header dicts as they are finalized by GRANDPA.
        Each header contains:
        - number: hex-encoded block number
        - parentHash: 0x-prefixed hex of parent block hash
        - stateRoot, extrinsicsRoot

        On connection failure, automatically reconnects with backoff.
        """
        backoff = 1
        max_backoff = 60

        while True:
            try:
                subscription = self.substrate.subscribe_block_headers(
                    finalized_only=True
                )
                backoff = 1  # Reset on successful connection

                for header in subscription:
                    yield header
            except (
                SubstrateRequestException,
                ConnectionError,
                OSError,
                BrokenPipeError,
            ) as e:
                logger.error(
                    f"Subscription lost: {e}. "
                    f"Reconnecting in {backoff}s..."
                )
                time.sleep(backoff)
                backoff = min(backoff * 2, max_backoff)
                try:
                    self.reconnect()
                except Exception as re:
                    logger.error(f"Reconnect failed: {re}")
            except KeyboardInterrupt:
                logger.info("Mining interrupted by user")
                return

    def submit_mining_proof(
        self,
        vqe_params: list[int],
        energy: int,
        hamiltonian_seed: bytes,
        n_qubits: int,
    ) -> Optional[str]:
        """
        Submit a VQE mining proof to the Substrate node.

        Constructs and signs the QbcConsensus::submit_mining_proof extrinsic,
        then submits it and waits for inclusion.

        Args:
            vqe_params: VQE parameters as i64 values (scaled by 10^12)
            energy: Ground state energy as i128 (scaled by 10^12)
            hamiltonian_seed: 32-byte Hamiltonian seed
            n_qubits: Number of qubits used

        Returns:
            Extrinsic hash hex string if submitted, None on failure.
        """
        # The miner_address parameter is ignored by the pallet (derived from origin),
        # but we must still provide it for the call signature.
        # Use a zero address — the pallet will override it.
        miner_address = list(bytes(32))

        call = self.substrate.compose_call(
            call_module="QbcConsensus",
            call_function="submit_mining_proof",
            call_params={
                "miner_address": {"value": miner_address},
                "vqe_proof": {
                    "params": vqe_params,
                    "energy": energy,
                    "hamiltonian_seed": f"0x{hamiltonian_seed.hex()}",
                    "n_qubits": n_qubits,
                },
            },
        )

        extrinsic = self.substrate.create_signed_extrinsic(
            call=call,
            keypair=self.keypair,
        )

        try:
            receipt = self.substrate.submit_extrinsic(
                extrinsic,
                wait_for_inclusion=True,
            )

            if receipt.is_success:
                logger.info(
                    f"Mining proof accepted! "
                    f"Block: {receipt.block_hash}, "
                    f"Extrinsic: {receipt.extrinsic_hash}"
                )
                return receipt.extrinsic_hash
            else:
                logger.error(
                    f"Mining proof REJECTED: {receipt.error_message}"
                )
                return None

        except SubstrateRequestException as e:
            logger.error(f"Failed to submit mining proof: {e}")
            return None

    def close(self) -> None:
        """Close the WebSocket connection."""
        if self.substrate:
            try:
                self.substrate.close()
            except Exception:
                pass
