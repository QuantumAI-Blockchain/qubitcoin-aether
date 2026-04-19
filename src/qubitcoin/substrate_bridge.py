"""
Substrate Bridge — connects the Python execution service to the Substrate consensus node.

In hybrid mode (SUBSTRATE_MODE=true), the Substrate node handles L1 consensus
(block production, UTXO validation, P2P) while this bridge:
- Subscribes to finalized blocks via WebSocket
- Triggers QVM/Aether processing for each block
- Submits mining proofs as signed extrinsics
- Anchors Aether Phi and QVM state roots via Sudo extrinsics
- Mirrors block data to CockroachDB for RPC query purposes
"""

import asyncio
import json
import time
from typing import Any, Callable, Coroutine, Optional

import httpx
import websockets
from websockets.exceptions import ConnectionClosed

from .config import Config
from .utils.logger import get_logger

logger = get_logger(__name__)

# Scale factor for difficulty (matches primitives/lib.rs: Difficulty = u64, 10^6)
DIFFICULTY_SCALE: int = 1_000_000
# Scale factor for QBC amounts (1 QBC = 10^8 units)
QBC_UNIT: int = 100_000_000
# Scale factor for VQE energy/params (10^12)
ENERGY_SCALE: int = 1_000_000_000_000
# Scale factor for Phi (10^3)
PHI_SCALE: int = 1_000


class SubstrateBridge:
    """Bridge between Python execution service and Substrate consensus node.

    Connects via WebSocket to subscribe to finalized block headers, fetches
    full block data, and triggers the Python processing pipeline for each block.
    """

    def __init__(
        self,
        ws_url: str = "",
        http_url: str = "",
        sudo_seed: str = "",
    ) -> None:
        self.ws_url: str = ws_url or Config.SUBSTRATE_WS_URL
        self.http_url: str = http_url or Config.SUBSTRATE_HTTP_URL
        self.sudo_seed: str = sudo_seed or Config.SUBSTRATE_SUDO_SEED
        self._ws: Optional[websockets.WebSocketClientProtocol] = None
        self._subscription_id: Optional[str] = None
        self._running: bool = False
        self._reconnect_delay: float = 1.0
        self._max_reconnect_delay: float = 30.0
        self._block_callback: Optional[Callable[..., Coroutine[Any, Any, None]]] = None
        self._last_finalized_height: int = -1
        self._cached_chain_info: dict = {}
        self._chain_info_updated: float = 0
        self._last_block_time: float = 0.0
        self._rpc_id: int = 0
        # Optional: substrate-interface for extrinsic encoding
        self._substrate: Any = None

    # ──────────────────────────────────────────────────────────────────────
    # Connection management
    # ──────────────────────────────────────────────────────────────────────

    async def connect(self) -> bool:
        """Establish WebSocket connection to Substrate node."""
        try:
            self._ws = await websockets.connect(
                self.ws_url,
                ping_interval=20,
                ping_timeout=20,
                close_timeout=10,
                max_size=10 * 1024 * 1024,  # 10MB max message
            )
            logger.info(f"Connected to Substrate node at {self.ws_url}")
            self._reconnect_delay = 1.0
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Substrate node: {e}")
            return False

    async def disconnect(self) -> None:
        """Close WebSocket connection."""
        self._running = False
        if self._ws:
            try:
                await self._ws.close()
            except Exception:
                pass
            self._ws = None
        logger.info("Disconnected from Substrate node")

    def _next_rpc_id(self) -> int:
        self._rpc_id += 1
        return self._rpc_id

    async def _rpc_call(self, method: str, params: list | None = None) -> Any:
        """Send a JSON-RPC call via HTTP (avoids WebSocket contention)."""
        rpc_id = self._next_rpc_id()
        request = {
            "jsonrpc": "2.0",
            "id": rpc_id,
            "method": method,
            "params": params or [],
        }
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(self.http_url, json=request)
            resp.raise_for_status()
            data = resp.json()
            if "error" in data:
                raise RuntimeError(
                    f"RPC error: {data['error'].get('message', data['error'])}"
                )
            return data.get("result")

    async def _ws_rpc_call(self, method: str, params: list | None = None) -> Any:
        """Send a JSON-RPC call over WebSocket (for subscription setup only)."""
        if not self._ws:
            raise ConnectionError("Not connected to Substrate node")

        rpc_id = self._next_rpc_id()
        request = {
            "jsonrpc": "2.0",
            "id": rpc_id,
            "method": method,
            "params": params or [],
        }
        await self._ws.send(json.dumps(request))

        # Wait for matching response (skip subscription notifications)
        while True:
            raw = await asyncio.wait_for(self._ws.recv(), timeout=30)
            response = json.loads(raw)
            if response.get("id") == rpc_id:
                if "error" in response:
                    raise RuntimeError(
                        f"RPC error: {response['error'].get('message', response['error'])}"
                    )
                return response.get("result")
            # Re-queue subscription notifications for the listener
            if "method" in response and response["method"] in ("chain_newHead", "chain_finalizedHead"):
                if self._block_callback:
                    header = response.get("params", {}).get("result", {})
                    if header:
                        asyncio.create_task(self._process_header(header))

    # ──────────────────────────────────────────────────────────────────────
    # Block subscription
    # ──────────────────────────────────────────────────────────────────────

    async def subscribe_finalized_blocks(
        self,
        on_block: Callable[..., Coroutine[Any, Any, None]],
    ) -> None:
        """Subscribe to finalized block headers and call on_block for each.

        Handles reconnection automatically. Runs until disconnect() is called.
        """
        self._block_callback = on_block
        self._running = True

        while self._running:
            try:
                if not self._ws:
                    connected = await self.connect()
                    if not connected:
                        await asyncio.sleep(self._reconnect_delay)
                        self._reconnect_delay = min(
                            self._reconnect_delay * 2, self._max_reconnect_delay
                        )
                        continue

                # Subscribe to new heads (not finalized — single-validator finalization
                # can stall, blocking Aether Tree processing entirely)
                result = await self._ws_rpc_call("chain_subscribeNewHeads")
                self._subscription_id = result
                logger.info(f"Subscribed to new heads (sub_id={result})")

                # Listen for notifications
                await self._listen_loop()

            except ConnectionClosed as e:
                logger.warning(f"WebSocket connection closed: {e}")
                self._ws = None
                if self._running:
                    logger.info(
                        f"Reconnecting in {self._reconnect_delay:.1f}s..."
                    )
                    await asyncio.sleep(self._reconnect_delay)
                    self._reconnect_delay = min(
                        self._reconnect_delay * 2, self._max_reconnect_delay
                    )
            except Exception as e:
                logger.error(f"Block subscription error: {e}", exc_info=True)
                self._ws = None
                if self._running:
                    await asyncio.sleep(self._reconnect_delay)
                    self._reconnect_delay = min(
                        self._reconnect_delay * 2, self._max_reconnect_delay
                    )

    async def _listen_loop(self) -> None:
        """Listen for subscription notifications on the WebSocket."""
        while self._running and self._ws:
            try:
                raw = await asyncio.wait_for(self._ws.recv(), timeout=30)
                msg = json.loads(raw)

                # Subscription notification (chain_newHead for new heads subscription)
                if msg.get("method") in ("chain_newHead", "chain_finalizedHead"):
                    header = msg.get("params", {}).get("result", {})
                    if header:
                        # Fire-and-forget: don't block the listener loop
                        # so the event loop stays responsive for API requests
                        asyncio.create_task(self._process_header(header))
            except asyncio.TimeoutError:
                # No message in 30s — send a health check
                try:
                    await self._rpc_call("system_health")
                except Exception:
                    raise ConnectionClosed(None, None)
            except ConnectionClosed:
                raise
            except Exception as e:
                logger.error(f"Error in listen loop: {e}", exc_info=True)

    async def _process_header(self, header: dict) -> None:
        """Process a finalized block header notification."""
        try:
            # Parse block number from hex
            number_hex = header.get("number", "0x0")
            block_height = int(number_hex, 16)

            # Skip if we already processed this height
            if block_height <= self._last_finalized_height:
                return

            self._last_finalized_height = block_height
            self._last_block_time = time.time()

            # Update cached chain info for fast API responses
            block_hash_from_header = header.get("parentHash", "")  # Will be updated below
            self._update_cache_from_header(block_height, block_hash_from_header)

            # Fetch parent hash for reference
            parent_hash = header.get("parentHash", "0x" + "0" * 64)

            # Fetch full block data
            block_hash = await self._get_block_hash(block_height)
            block_data = await self.fetch_block(block_hash)

            if block_data and self._block_callback:
                await self._block_callback(block_height, block_hash, header, block_data)

        except Exception as e:
            logger.error(
                f"Error processing block header: {e}", exc_info=True
            )

    # ──────────────────────────────────────────────────────────────────────
    # Block data fetching
    # ──────────────────────────────────────────────────────────────────────

    async def _get_block_hash(self, block_number: int) -> str:
        """Get block hash by number."""
        result = await self._rpc_call("chain_getBlockHash", [block_number])
        return result or ("0x" + "0" * 64)

    async def fetch_block(self, block_hash: str) -> Optional[dict]:
        """Fetch full block data by hash."""
        try:
            result = await self._rpc_call("chain_getBlock", [block_hash])
            if result and "block" in result:
                block = result["block"]
                return {
                    "header": block.get("header", {}),
                    "extrinsics": block.get("extrinsics", []),
                    "block_hash": block_hash,
                }
            return None
        except Exception as e:
            logger.error(f"Failed to fetch block {block_hash}: {e}")
            return None

    async def get_chain_info(self) -> dict:
        """Get current chain information from Substrate node.

        Returns cached info if available and fresh (< 10s old).
        Falls back to live RPC calls if cache is stale.
        """
        import time

        # Return cache if fresh (< 10 seconds old)
        if self._cached_chain_info and (time.time() - self._chain_info_updated) < 10:
            return self._cached_chain_info

        try:
            if not self._ws:
                await self.connect()

            health = await self._rpc_call("system_health")
            chain = await self._rpc_call("system_chain")
            version = await self._rpc_call("system_version")

            # Get best (head) block — this is the real chain tip
            best_header = await self._rpc_call("chain_getHeader")
            best_number = 0
            if best_header and "number" in best_header:
                best_number = int(best_header["number"], 16)

            # Get finalized block separately
            finalized_hash = await self._rpc_call("chain_getFinalizedHead")
            finalized_header = await self._rpc_call("chain_getHeader", [finalized_hash])
            finalized_number = 0
            if finalized_header and "number" in finalized_header:
                finalized_number = int(finalized_header["number"], 16)

            # Fork offset: Substrate block 0 = Python block 208,680
            fork_offset = 208680

            info = {
                "chain": chain,
                "version": version,
                "health": health,
                "best_number": best_number,
                "best_height": fork_offset + best_number,
                "finalized_height": finalized_number,
                "finalized_hash": finalized_hash,
                "fork_offset": fork_offset,
                "substrate_node": True,
            }
            self._cached_chain_info = info
            self._chain_info_updated = time.time()
            return info
        except Exception as e:
            logger.error(f"Failed to get chain info: {e}")
            # Return stale cache if available
            if self._cached_chain_info:
                return self._cached_chain_info
            return {
                "chain": "Qubitcoin",
                "version": "unknown",
                "health": {"peers": 0, "isSyncing": True},
                "finalized_height": 0,
                "finalized_hash": "0x" + "0" * 64,
                "substrate_node": True,
                "error": str(e),
            }

    def _update_cache_from_header(self, block_height: int, block_hash: str) -> None:
        """Update cached chain info from a received block header (non-async)."""
        import time
        fork_offset = 208680
        if self._cached_chain_info:
            self._cached_chain_info["best_number"] = block_height
            self._cached_chain_info["best_height"] = fork_offset + block_height
            self._chain_info_updated = time.time()

    # ──────────────────────────────────────────────────────────────────────
    # Extrinsic submission
    # ──────────────────────────────────────────────────────────────────────

    def _get_substrate_interface(self) -> Any:
        """Lazily initialize substrate-interface for extrinsic encoding."""
        if self._substrate is None:
            try:
                from substrateinterface import SubstrateInterface, Keypair
                self._substrate = SubstrateInterface(url=self.http_url)
                self._keypair = Keypair.create_from_uri(self.sudo_seed)
                logger.info("SubstrateInterface initialized for extrinsic submission")
            except ImportError:
                logger.warning(
                    "substrate-interface not installed — "
                    "extrinsic submission will not work. "
                    "Install with: pip install substrate-interface"
                )
                raise
            except Exception as e:
                logger.error(f"SubstrateInterface init failed: {e}")
                raise
        return self._substrate

    async def submit_mining_proof(self, vqe_proof: dict) -> Optional[str]:
        """Submit a VQE mining proof to Substrate as a signed extrinsic.

        Args:
            vqe_proof: Dict with keys: params (list[float]), energy (float),
                       hamiltonian_seed (str), n_qubits (int)

        Returns:
            Extrinsic hash if successful, None otherwise.
        """
        try:
            substrate = self._get_substrate_interface()

            # Convert Python floats to fixed-point integers for SCALE encoding
            params_scaled = [
                int(p * ENERGY_SCALE) for p in vqe_proof["params"]
            ]
            energy_scaled = int(vqe_proof["energy"] * ENERGY_SCALE)
            hamiltonian_seed = vqe_proof["hamiltonian_seed"]
            if isinstance(hamiltonian_seed, str) and hamiltonian_seed.startswith("0x"):
                hamiltonian_seed = hamiltonian_seed
            n_qubits = vqe_proof.get("n_qubits", 4)

            call = substrate.compose_call(
                call_module="QbcConsensus",
                call_function="submit_mining_proof",
                call_params={
                    "proof": {
                        "params": params_scaled,
                        "energy": energy_scaled,
                        "hamiltonian_seed": hamiltonian_seed,
                        "n_qubits": n_qubits,
                    }
                },
            )

            extrinsic = substrate.create_signed_extrinsic(
                call=call, keypair=self._keypair
            )
            result = substrate.submit_extrinsic(
                extrinsic, wait_for_inclusion=False
            )
            tx_hash = result.get("extrinsic_hash", str(result))
            logger.info(f"Mining proof submitted: {tx_hash}")
            return tx_hash

        except Exception as e:
            logger.error(f"Failed to submit mining proof: {e}", exc_info=True)
            return None

    async def anchor_aether_state(
        self,
        block_height: int,
        phi_value: float,
        knowledge_root: str,
        knowledge_nodes: int,
        knowledge_edges: int,
    ) -> Optional[str]:
        """Anchor Aether Tree state to Substrate via Sudo extrinsic.

        Uses Sudo.sudo() because pallet-qbc-aether-anchor::record_block_state
        requires ensure_root origin.
        """
        try:
            substrate = self._get_substrate_interface()

            phi_scaled = int(phi_value * PHI_SCALE)
            kr_bytes = bytes.fromhex(
                knowledge_root.replace("0x", "")
            ) if knowledge_root else b"\x00" * 32

            inner_call = substrate.compose_call(
                call_module="QbcAetherAnchor",
                call_function="record_block_state",
                call_params={
                    "block_height": block_height,
                    "phi": {
                        "block_height": block_height,
                        "phi_scaled": phi_scaled,
                        "knowledge_nodes": knowledge_nodes,
                        "knowledge_edges": knowledge_edges,
                    },
                    "knowledge_root": f"0x{kr_bytes.hex()}",
                },
            )

            sudo_call = substrate.compose_call(
                call_module="Sudo",
                call_function="sudo",
                call_params={"call": inner_call},
            )

            extrinsic = substrate.create_signed_extrinsic(
                call=sudo_call, keypair=self._keypair
            )
            result = substrate.submit_extrinsic(
                extrinsic, wait_for_inclusion=False
            )
            tx_hash = result.get("extrinsic_hash", str(result))
            logger.debug(f"Aether state anchored at height {block_height}: {tx_hash}")
            return tx_hash

        except Exception as e:
            logger.error(f"Failed to anchor Aether state: {e}", exc_info=True)
            return None

    async def anchor_qvm_state(
        self,
        block_height: int,
        state_root: str,
    ) -> Optional[str]:
        """Anchor QVM state root to Substrate via Sudo extrinsic."""
        try:
            substrate = self._get_substrate_interface()

            inner_call = substrate.compose_call(
                call_module="QbcQvmAnchor",
                call_function="update_state_root",
                call_params={
                    "block_height": block_height,
                    "state_root": state_root,
                },
            )

            sudo_call = substrate.compose_call(
                call_module="Sudo",
                call_function="sudo",
                call_params={"call": inner_call},
            )

            extrinsic = substrate.create_signed_extrinsic(
                call=sudo_call, keypair=self._keypair
            )
            result = substrate.submit_extrinsic(
                extrinsic, wait_for_inclusion=False
            )
            tx_hash = result.get("extrinsic_hash", str(result))
            logger.debug(f"QVM state root anchored at height {block_height}: {tx_hash}")
            return tx_hash

        except Exception as e:
            logger.error(f"Failed to anchor QVM state root: {e}", exc_info=True)
            return None

    # ──────────────────────────────────────────────────────────────────────
    # Utility queries
    # ──────────────────────────────────────────────────────────────────────

    async def get_runtime_version(self) -> dict:
        """Get runtime version info."""
        try:
            return await self._rpc_call("state_getRuntimeVersion") or {}
        except Exception:
            return {}

    async def get_system_health(self) -> dict:
        """Get system health."""
        try:
            return await self._rpc_call("system_health") or {}
        except Exception:
            return {"peers": 0, "isSyncing": True}

    @property
    def is_connected(self) -> bool:
        """Check if WebSocket is connected (or recently processed a block)."""
        # If we recently processed blocks, we're connected even if WS check fails
        if self._last_finalized_height > 0:
            import time as _time
            # Consider connected if we processed a block in the last 30 seconds
            if hasattr(self, '_last_block_time') and (_time.time() - self._last_block_time) < 30:
                return True
        if self._ws is None:
            return False
        try:
            return bool(self._ws.open)
        except AttributeError:
            try:
                from websockets.protocol import State
                return self._ws.state == State.OPEN
            except Exception:
                return self._ws is not None

    @property
    def last_finalized_height(self) -> int:
        """Return the last finalized block height seen."""
        return self._last_finalized_height
