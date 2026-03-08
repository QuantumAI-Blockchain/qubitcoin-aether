"""
Python gRPC client for Rust P2P network.
Bridges Python blockchain with Rust libp2p networking.

Supports:
- Outbound: BroadcastBlock, BroadcastTransaction, SubmitBlock
- Inbound:  StreamBlocks, StreamTransactions, StreamEvents (async generators)
- Queries:  GetPeerStats, GetPeerList, HealthCheck
"""
import asyncio
import sys
import os
from typing import Callable, Optional

from ..utils.logger import get_logger

logger = get_logger(__name__)

# Import gRPC and generated protobuf files
try:
    import grpc
    import grpc.aio

    rust_p2p_path = os.path.join(os.path.dirname(__file__), '../../../rust-p2p/src/bridge')
    rust_p2p_path = os.path.abspath(rust_p2p_path)
    if rust_p2p_path not in sys.path:
        sys.path.insert(0, rust_p2p_path)

    import p2p_service_pb2
    import p2p_service_pb2_grpc
    GRPC_AVAILABLE = True
except ImportError as e:
    logger.warning(f"gRPC not available: {e}")
    grpc = None  # type: ignore[assignment]
    p2p_service_pb2 = None
    p2p_service_pb2_grpc = None
    GRPC_AVAILABLE = False


class RustP2PClient:
    """
    Client for Rust P2P network via gRPC.
    Handles block/transaction broadcasting, streaming, and peer statistics.
    """

    def __init__(self, grpc_addr: str = "127.0.0.1:50051"):
        self.grpc_addr = grpc_addr
        self.channel = None
        self.async_channel = None
        self.stub = None
        self.async_stub = None
        self.connected = False
        self._stream_tasks: list[asyncio.Task] = []

        if not GRPC_AVAILABLE:
            logger.warning("gRPC not available - Rust P2P client disabled")

    def connect(self) -> bool:
        """Connect to Rust P2P gRPC server (synchronous channel)."""
        if not GRPC_AVAILABLE:
            logger.error("gRPC proto not available - cannot connect")
            return False

        try:
            self.channel = grpc.insecure_channel(self.grpc_addr)
            self.stub = p2p_service_pb2_grpc.P2PStub(self.channel)

            # Test connection with health check
            stats = self.get_peer_stats()
            if stats is not None:
                self.connected = True
                logger.info(f"Connected to Rust P2P at {self.grpc_addr}")
                logger.info(f"Peers: {stats.get('peer_count', 0)}")
                return True
            else:
                logger.error("Failed to get stats from Rust P2P")
                return False

        except Exception as e:
            logger.error(f"Failed to connect to Rust P2P: {e}")
            self.connected = False
            return False

    async def connect_async(self) -> bool:
        """Connect async channel for streaming RPCs."""
        if not GRPC_AVAILABLE:
            return False

        try:
            self.async_channel = grpc.aio.insecure_channel(self.grpc_addr)
            self.async_stub = p2p_service_pb2_grpc.P2PStub(self.async_channel)
            return True
        except Exception as e:
            logger.error(f"Failed to create async gRPC channel: {e}")
            return False

    # ── Outbound RPCs ───────────────────────────────────────────────

    def broadcast_block(self, height: int, block_hash: str) -> bool:
        """Broadcast new block announcement to P2P network."""
        if not self.connected or not self.stub:
            logger.warning("Not connected to Rust P2P - cannot broadcast block")
            return False

        try:
            request = p2p_service_pb2.BroadcastBlockRequest(
                height=height,
                hash=block_hash
            )
            response = self.stub.BroadcastBlock(request, timeout=3.0)

            if response.success:
                logger.info(f"Block {height} broadcasted via Rust P2P")
                return True
            else:
                logger.warning(f"Block broadcast failed: {response.message}")
                return False

        except grpc.RpcError as e:
            logger.error(f"gRPC error broadcasting block: {e.code()}: {e.details()}")
            return False
        except Exception as e:
            logger.error(f"Error broadcasting block: {e}")
            return False

    def broadcast_transaction(self, txid: str, size: int, fee: str) -> bool:
        """Broadcast transaction to P2P network."""
        if not self.connected or not self.stub:
            logger.warning("Not connected to Rust P2P - cannot broadcast tx")
            return False

        try:
            request = p2p_service_pb2.BroadcastTransactionRequest(
                txid=txid,
                size=size,
                fee=fee
            )
            response = self.stub.BroadcastTransaction(request, timeout=3.0)

            if response.success:
                logger.debug(f"Tx {txid[:8]} broadcasted via Rust P2P")
                return True
            else:
                logger.warning(f"Tx broadcast failed: {response.message}")
                return False

        except grpc.RpcError as e:
            logger.error(f"gRPC error broadcasting tx: {e.code()}: {e.details()}")
            return False
        except Exception as e:
            logger.error(f"Error broadcasting tx: {e}")
            return False

    def submit_block(self, height: int, block_hash: str, prev_hash: str,
                     timestamp: int, difficulty: float, nonce: int,
                     miner: str) -> bool:
        """Submit full block data for propagation (used for mined blocks)."""
        if not self.connected or not self.stub:
            logger.warning("Not connected to Rust P2P - cannot submit block")
            return False

        try:
            request = p2p_service_pb2.BlockData(
                height=height,
                hash=block_hash,
                prev_hash=prev_hash,
                timestamp=timestamp,
                difficulty=difficulty,
                nonce=nonce,
                miner=miner
            )
            response = self.stub.SubmitBlock(request, timeout=10.0)

            if response.success:
                logger.info(f"Full block {height} submitted to Rust P2P")
                return True
            else:
                logger.warning(f"Block submit failed: {response.message}")
                return False

        except grpc.RpcError as e:
            logger.error(f"gRPC error submitting block: {e.code()}: {e.details()}")
            return False
        except Exception as e:
            logger.error(f"Error submitting block: {e}")
            return False

    # ── Streaming RPCs ──────────────────────────────────────────────

    async def stream_blocks(self, on_block: Callable) -> None:
        """Stream blocks from P2P network. Calls on_block(block_dict) for each.

        Args:
            on_block: Callback receiving dict with height, hash, prev_hash,
                      timestamp, difficulty, nonce, miner.
        """
        if not self.async_stub:
            if not await self.connect_async():
                return

        request = p2p_service_pb2.StreamRequest()
        logger.info("Subscribing to Rust P2P block stream...")

        try:
            stream = self.async_stub.StreamBlocks(request)
            async for block in stream:
                block_dict = {
                    'height': block.height,
                    'hash': block.hash,
                    'prev_hash': block.prev_hash,
                    'timestamp': block.timestamp,
                    'difficulty': block.difficulty,
                    'nonce': block.nonce,
                    'miner': block.miner,
                }
                logger.info(f"Block received from P2P stream: height={block.height}")
                try:
                    if asyncio.iscoroutinefunction(on_block):
                        await on_block(block_dict)
                    else:
                        on_block(block_dict)
                except Exception as e:
                    logger.error(f"Error processing streamed block: {e}")

        except grpc.aio.AioRpcError as e:
            if e.code() == grpc.StatusCode.CANCELLED:
                logger.info("Block stream cancelled")
            else:
                logger.error(f"Block stream error: {e.code()}: {e.details()}")
        except Exception as e:
            logger.error(f"Block stream failed: {e}")

    async def stream_transactions(self, on_tx: Callable) -> None:
        """Stream transactions from P2P network. Calls on_tx(tx_dict) for each.

        Args:
            on_tx: Callback receiving dict with txid, size, fee.
        """
        if not self.async_stub:
            if not await self.connect_async():
                return

        request = p2p_service_pb2.StreamRequest()
        logger.info("Subscribing to Rust P2P transaction stream...")

        try:
            stream = self.async_stub.StreamTransactions(request)
            async for tx in stream:
                tx_dict = {
                    'txid': tx.txid,
                    'size': tx.size,
                    'fee': tx.fee,
                }
                logger.debug(f"Tx received from P2P stream: {tx.txid[:8]}")
                try:
                    if asyncio.iscoroutinefunction(on_tx):
                        await on_tx(tx_dict)
                    else:
                        on_tx(tx_dict)
                except Exception as e:
                    logger.error(f"Error processing streamed tx: {e}")

        except grpc.aio.AioRpcError as e:
            if e.code() == grpc.StatusCode.CANCELLED:
                logger.info("Transaction stream cancelled")
            else:
                logger.error(f"Transaction stream error: {e.code()}: {e.details()}")
        except Exception as e:
            logger.error(f"Transaction stream failed: {e}")

    async def start_streaming(self, on_block: Optional[Callable] = None,
                              on_tx: Optional[Callable] = None) -> None:
        """Start block and/or transaction streaming as background tasks.

        Args:
            on_block: Callback for received blocks.
            on_tx: Callback for received transactions.
        """
        if on_block:
            task = asyncio.create_task(self.stream_blocks(on_block))
            self._stream_tasks.append(task)

        if on_tx:
            task = asyncio.create_task(self.stream_transactions(on_tx))
            self._stream_tasks.append(task)

    def stop_streaming(self) -> None:
        """Cancel all active stream tasks."""
        for task in self._stream_tasks:
            task.cancel()
        self._stream_tasks.clear()

    # ── Query RPCs ──────────────────────────────────────────────────

    def get_peer_stats(self) -> Optional[dict]:
        """Get P2P network statistics."""
        if not self.stub:
            return None

        try:
            request = p2p_service_pb2.PeerStatsRequest()
            response = self.stub.GetPeerStats(request, timeout=3.0)

            return {
                'peer_count': response.peer_count,
                'gossipsub_peers': response.gossipsub_peers,
                'blocks_received': response.blocks_received,
                'blocks_sent': response.blocks_sent,
                'txs_received': response.txs_received,
                'txs_sent': response.txs_sent,
                'uptime_seconds': response.uptime_seconds,
                'connected': True,
            }

        except Exception as e:
            logger.debug(f"Failed to get peer stats: {e}")
            self.connected = False
            return None

    def get_peer_list(self) -> list[dict]:
        """Get detailed list of connected peers."""
        if not self.connected or not self.stub:
            return []

        try:
            request = p2p_service_pb2.PeerListRequest()
            response = self.stub.GetPeerList(request, timeout=3.0)

            return [
                {
                    'peer_id': p.peer_id,
                    'address': p.address,
                    'last_seen': p.last_seen,
                    'agent_version': p.agent_version,
                    'protocol_version': p.protocol_version,
                    'latency_ms': p.latency_ms,
                }
                for p in response.peers
            ]

        except Exception as e:
            logger.debug(f"Failed to get peer list: {e}")
            return []

    def health_check(self) -> Optional[dict]:
        """Check health of Rust P2P daemon."""
        if not self.stub:
            return None

        try:
            request = p2p_service_pb2.HealthRequest()
            response = self.stub.HealthCheck(request, timeout=3.0)

            return {
                'healthy': response.healthy,
                'version': response.version,
                'peer_count': response.peer_count,
                'uptime_seconds': response.uptime_seconds,
            }

        except Exception as e:
            logger.debug(f"Health check failed: {e}")
            return None

    def get_peer_count(self) -> int:
        """Get number of connected peers."""
        stats = self.get_peer_stats()
        return stats.get('peer_count', 0) if stats else 0

    def disconnect(self) -> None:
        """Close all gRPC connections and stop streams."""
        self.stop_streaming()
        if self.channel:
            self.channel.close()
            self.channel = None
        if self.async_channel:
            # async channel close is best-effort
            try:
                asyncio.get_event_loop().create_task(self.async_channel.close())
            except RuntimeError:
                pass
            self.async_channel = None
        self.stub = None
        self.async_stub = None
        self.connected = False
        logger.info("Disconnected from Rust P2P")
