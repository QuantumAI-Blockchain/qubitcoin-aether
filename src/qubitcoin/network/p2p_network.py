"""
Qubitcoin P2P Network Module
Handles peer-to-peer communication, block propagation, and network consensus
"""
import asyncio
import json
import time
import hashlib
from typing import Dict, List, Set, Optional, Callable, Any
from dataclasses import dataclass, asdict
from datetime import datetime
from collections import defaultdict
from ..config import Config
from ..database.models import Block
from ..consensus.engine import ConsensusEngine  # For validation/reorg
from ..utils.logger import get_logger
logger = get_logger(__name__)
@dataclass
class Message:
    """P2P network message"""
    type: str # 'block', 'transaction', 'ping', 'pong', 'get_peers', 'peers', 'get_height', 'height', 'get_block'
    data: Any
    timestamp: float
    sender_id: str
    msg_id: str
    def to_json(self) -> str:
        """Serialize to JSON"""
        return json.dumps({
            'type': self.type,
            'data': self.data,
            'timestamp': self.timestamp,
            'sender_id': self.sender_id,
            'msg_id': self.msg_id
        })
    @classmethod
    def from_json(cls, json_str: str) -> 'Message':
        """Deserialize from JSON"""
        data = json.loads(json_str)
        return cls(**data)
@dataclass
class Peer:
    """Connected peer information"""
    peer_id: str
    host: str
    port: int
    connected_at: datetime
    last_seen: datetime
    score: int = 100 # Reputation score (0-100)
    messages_sent: int = 0
    messages_received: int = 0
    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            'peer_id': self.peer_id,
            'host': self.host,
            'port': self.port,
            'connected_at': self.connected_at.isoformat(),
            'last_seen': self.last_seen.isoformat(),
            'score': self.score,
            'messages_sent': self.messages_sent,
            'messages_received': self.messages_received
        }
class P2PNetwork:
    """
    Peer-to-peer networking layer for Qubitcoin
    Handles node discovery, message propagation, and consensus
    """
    def __init__(self, port: int, peer_id: str, consensus: ConsensusEngine,  # Consensus for reorg
                 max_peers: int = 50):
        """
        Initialize P2P network
        Args:
            port: Port to listen on
            peer_id: Unique identifier for this node
            consensus: Consensus engine for validation/reorg
            max_peers: Maximum number of concurrent peer connections
        """
        self.port = port
        self.peer_id = peer_id
        self.consensus = consensus
        self.max_peers = max_peers
        # Connection management
        self.server: Optional[asyncio.Server] = None
        self.connections: Dict[str, Peer] = {} # peer_id -> Peer
        self.writers: Dict[str, asyncio.StreamWriter] = {} # peer_id -> writer
        # Message handling
        self.handlers: Dict[str, Callable] = {}
        self.seen_messages: Set[str] = set() # Message deduplication
        self.message_cache_size = 10000
        # Statistics
        self.stats = {
            'messages_sent': 0,
            'messages_received': 0,
            'blocks_propagated': 0,
            'txs_propagated': 0,
            'connections_made': 0,
            'connections_dropped': 0
        }
        # Running state
        self.running = False
        logger.info(f"P2P Network initialized on port {port}, peer_id: {self.peer_id}")
    def register_handler(self, message_type: str, handler: Callable):
        """
        Register a message handler
        Args:
            message_type: Type of message to handle
            handler: Async function to handle message (message, sender_id)
        """
        self.handlers[message_type] = handler
        logger.debug(f"Registered handler for message type: {message_type}")
    async def start(self):
        """Start P2P network server"""
        self.running = True
        # Start TCP server
        self.server = await asyncio.start_server(
            self._handle_connection,
            '0.0.0.0',
            self.port
        )
        logger.info(f"🌐 P2P server listening on port {self.port}")
        # Bootstrap seeds (fix: parse str to list if not)
        seeds = Config.PEER_SEEDS
        if isinstance(seeds, str):
            seeds = seeds.split(',') if ',' in seeds else [seeds]  # Fix parse
        if seeds:
            for seed in seeds:
                # Parse seed format: /ip4/host/tcp/port/p2p/peer_id
                parts = seed.strip().split('/')
                if len(parts) >= 7:
                    host = parts[2]
                    port = int(parts[4])
                    await self.connect_to_peer(f"{host}:{port}")
        # Start maintenance tasks
        asyncio.create_task(self._cleanup_loop())
        asyncio.create_task(self._peer_maintenance_loop())
    async def stop(self):
        """Stop P2P network server"""
        self.running = False
        # Close all connections
        for writer in self.writers.values():
            try:
                writer.close()
                await writer.wait_closed()
            except:
                pass
        # Close server
        if self.server:
            self.server.close()
            await self.server.wait_closed()
        logger.info("P2P network stopped")
    async def connect_to_peer(self, address: str):
        """
        Connect to a peer
        Args:
            address: Peer address in format "host:port"
        """
        try:
            host, port = address.split(':')
            port = int(port)
            # Don't connect to self
            if port == self.port:
                return
            # Check if already connected
            peer_id = f"{host}:{port}"
            if peer_id in self.connections:
                logger.debug(f"Already connected to {peer_id}")
                return
            # Check peer limit
            if len(self.connections) >= self.max_peers:
                logger.warning(f"Max peers ({self.max_peers}) reached, cannot connect to {peer_id}")
                return
            # Connect
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port),
                timeout=10.0
            )
            # Create peer entry
            peer = Peer(
                peer_id=peer_id,
                host=host,
                port=port,
                connected_at=datetime.now(),
                last_seen=datetime.now()
            )
            self.connections[peer_id] = peer
            self.writers[peer_id] = writer
            self.stats['connections_made'] += 1
            logger.info(f"✓ Connected to peer {peer_id}")
            # Start reading from this peer
            asyncio.create_task(self._read_from_peer(reader, writer, peer_id))
            # Send introduction
            await self.send_message(peer_id, 'ping', {
                'peer_id': self.peer_id,
                'timestamp': time.time()
            })
            # Request peers
            await self.send_message(peer_id, 'get_peers', {})
            # Request chain height
            await self.send_message(peer_id, 'get_height', {})
        except asyncio.TimeoutError:
            logger.warning(f"Connection timeout to {address}")
        except Exception as e:
            logger.error(f"Failed to connect to {address}: {e}")
    async def _handle_connection(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """Handle incoming connection"""
        addr = writer.get_extra_info('peername')
        peer_id = f"{addr[0]}:{addr[1]}"
        logger.info(f"📨 Incoming connection from {peer_id}")
        # Check peer limit
        if len(self.connections) >= self.max_peers:
            logger.warning(f"Max peers reached, rejecting {peer_id}")
            writer.close()
            await writer.wait_closed()
            return
        # Create peer entry
        peer = Peer(
            peer_id=peer_id,
            host=addr[0],
            port=addr[1],
            connected_at=datetime.now(),
            last_seen=datetime.now()
        )
        self.connections[peer_id] = peer
        self.writers[peer_id] = writer
        self.stats['connections_made'] += 1
        # Start reading
        asyncio.create_task(self._read_from_peer(reader, writer, peer_id))
    async def _read_from_peer(self, reader: asyncio.StreamReader,
                               writer: asyncio.StreamWriter, peer_id: str):
        """Read messages from peer"""
        MAX_MESSAGE_SIZE = 10_000_000  # 10MB max
        try:
            while self.running:
                # Read message length (4 bytes)
                length_bytes = await reader.readexactly(4)
                message_length = int.from_bytes(length_bytes, 'big')
                if message_length > MAX_MESSAGE_SIZE:
                    logger.warning(f"Message too large from {peer_id}: {message_length} bytes")
                    break
                if message_length == 0:
                    continue
                # Read message
                message_bytes = await reader.readexactly(message_length)
                message_str = message_bytes.decode('utf-8')
                # Parse message
                message = Message.from_json(message_str)
                # Update peer stats
                if peer_id in self.connections:
                    self.connections[peer_id].last_seen = datetime.now()
                    self.connections[peer_id].messages_received += 1
                self.stats['messages_received'] += 1
                # Handle message
                await self._handle_message(message, peer_id)
        except asyncio.IncompleteReadError:
            logger.debug(f"Connection closed by {peer_id}")
        except Exception as e:
            logger.error(f"Error reading from {peer_id}: {e}")
        finally:
            await self._disconnect_peer(peer_id)
    async def _handle_message(self, message: Message, sender_id: str):
        """Handle received message"""
        # Check for duplicate (prevent loops)
        if message.msg_id in self.seen_messages:
            return
        # Add to seen messages
        self.seen_messages.add(message.msg_id)
        # Limit cache size
        if len(self.seen_messages) > self.message_cache_size:
            to_remove = list(self.seen_messages)[:self.message_cache_size // 10]
            for msg_id in to_remove:
                self.seen_messages.discard(msg_id)
        logger.debug(f"📩 Received {message.type} from {sender_id}")
        # Track block/tx propagation
        if message.type == 'block':
            self.stats['blocks_propagated'] += 1
            block_data = message.data
            block = Block.from_dict(block_data)
            prev_block = self.consensus.db.get_block(block.height - 1)
            valid, reason = self.consensus.validate_block(block, prev_block, self.consensus.db)
            if valid:
                # Record height BEFORE storing so reorg check is correct
                height_before = self.consensus.db.get_current_height()
                # Store block + supply update atomically in one session
                with self.consensus.db.get_session() as session:
                    self.consensus.db.store_block(block, session=session)
                    for tx in block.transactions:
                        if not tx.inputs:  # coinbase
                            from decimal import Decimal
                            reward = sum(Decimal(str(o['amount'])) for o in tx.outputs)
                            self.consensus.db.update_supply(reward, session)
                            break
                    session.commit()
                logger.info(f"Stored block {block.height} from {sender_id}")
                await self._gossip_message(message, exclude=sender_id)
                # Trigger reorg if this block extends beyond our previous tip
                if block.height > height_before:
                    await self.consensus.resolve_fork(block, sender_id)
            else:
                logger.warning(f"Invalid block from {sender_id}: {reason}")
        elif message.type == 'transaction':
            self.stats['txs_propagated'] += 1
            # Validate/add to mempool (add if needed)
        elif message.type == 'get_height':
            await self.send_message(sender_id, 'height', {'height': self.consensus.db.get_current_height()})
        elif message.type == 'height':
            peer_height = message.data['height']
            if peer_height > self.consensus.db.get_current_height():
                logger.info(f"Peer {sender_id} has higher height {peer_height} - requesting block {peer_height}")
                await self.send_message(sender_id, 'get_block', {'height': peer_height})
        elif message.type == 'get_block':
            height = message.data['height']
            block = self.consensus.db.get_block(height)
            if block:
                await self.send_message(sender_id, 'block', block.to_dict())  # Assume added Block.to_dict
        # Call registered handler (skip warning for built-in types handled above)
        builtin_types = {'block', 'transaction', 'get_height', 'height', 'get_block', 'ping', 'pong', 'get_peers'}
        if message.type in self.handlers:
            try:
                await self.handlers[message.type](message, sender_id)
            except Exception as e:
                logger.error(f"Error in handler for {message.type}: {e}")
        elif message.type not in builtin_types:
            logger.warning(f"No handler for message type: {message.type}")
        # Gossip transactions (blocks already gossiped above on validation)
        if message.type == 'transaction':
            await self._gossip_message(message, exclude=sender_id)
    async def send_message(self, peer_id: str, msg_type: str, data: Any):
        """
        Send message to specific peer
        Args:
            peer_id: Target peer ID
            msg_type: Type of message
            data: Message data
        """
        if peer_id not in self.writers:
            logger.warning(f"Cannot send to {peer_id}: not connected")
            return
        try:
            message = Message(
                type=msg_type,
                data=data,
                timestamp=time.time(),
                sender_id=self.peer_id,
                msg_id=self._generate_msg_id(msg_type, data)
            )
            # Serialize
            message_str = message.to_json()
            message_bytes = message_str.encode('utf-8')
            # Send length + message
            length_bytes = len(message_bytes).to_bytes(4, 'big')
            writer = self.writers[peer_id]
            writer.write(length_bytes + message_bytes)
            await writer.drain()
            # Update stats
            if peer_id in self.connections:
                self.connections[peer_id].messages_sent += 1
            self.stats['messages_sent'] += 1
            logger.debug(f"📤 Sent {msg_type} to {peer_id}")
        except Exception as e:
            logger.error(f"Failed to send message to {peer_id}: {e}")
            await self._disconnect_peer(peer_id)
    async def broadcast(self, msg_type: str, data: Any, exclude: str = None):
        """
        Broadcast message to all peers
        Args:
            msg_type: Type of message
            data: Message data
            exclude: Optional peer ID to exclude
        """
        tasks = []
        for peer_id in list(self.connections.keys()):
            if peer_id != exclude:
                tasks.append(self.send_message(peer_id, msg_type, data))
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
            logger.info(f"📡 Broadcasted {msg_type} to {len(tasks)} peers")
    async def _gossip_message(self, message: Message, exclude: str):
        """
        Gossip message to other peers (except sender), preserving original msg_id
        for deduplication across relay hops.
        """
        for peer_id in list(self.connections.keys()):
            if peer_id != exclude:
                await self._forward_message(peer_id, message)

    async def _forward_message(self, peer_id: str, message: Message):
        """Forward an existing message preserving its msg_id for deduplication"""
        if peer_id not in self.writers:
            return
        try:
            message_str = message.to_json()
            message_bytes = message_str.encode('utf-8')
            length_bytes = len(message_bytes).to_bytes(4, 'big')
            writer = self.writers[peer_id]
            writer.write(length_bytes + message_bytes)
            await writer.drain()
            if peer_id in self.connections:
                self.connections[peer_id].messages_sent += 1
            self.stats['messages_sent'] += 1
        except Exception as e:
            logger.error(f"Failed to forward message to {peer_id}: {e}")
            await self._disconnect_peer(peer_id)
    async def _disconnect_peer(self, peer_id: str):
        """Disconnect from peer"""
        if peer_id in self.writers:
            try:
                self.writers[peer_id].close()
                await self.writers[peer_id].wait_closed()
            except:
                pass
            del self.writers[peer_id]
        if peer_id in self.connections:
            del self.connections[peer_id]
            self.stats['connections_dropped'] += 1
            logger.info(f"❌ Disconnected from {peer_id}")
    async def _cleanup_loop(self):
        """Periodic cleanup of message cache"""
        while self.running:
            await asyncio.sleep(300) # Every 5 minutes
            # Clean old messages
            if len(self.seen_messages) > self.message_cache_size:
                to_remove = list(self.seen_messages)[:self.message_cache_size // 2]
                for msg_id in to_remove:
                    self.seen_messages.discard(msg_id)
                logger.debug(f"Cleaned {len(to_remove)} old messages from cache")
    async def _peer_maintenance_loop(self):
        """Maintain peer connections and scores"""
        while self.running:
            await asyncio.sleep(60) # Every minute
            now = datetime.now()
            # Check for stale peers
            stale_peers = []
            for peer_id, peer in self.connections.items():
                time_since_seen = (now - peer.last_seen).total_seconds()
                # Disconnect if no activity for 5 minutes
                if time_since_seen > 300:
                    stale_peers.append(peer_id)
                    logger.warning(f"Peer {peer_id} stale (no activity for {time_since_seen:.0f}s)")
            # Disconnect stale peers
            for peer_id in stale_peers:
                await self._disconnect_peer(peer_id)
    def _generate_msg_id(self, msg_type: str, data: Any) -> str:
        """Generate unique message ID"""
        content = f"{msg_type}:{json.dumps(data, sort_keys=True)}:{time.time()}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]
    # ====================================================================
    # PEER SCORING & EVICTION
    # ====================================================================

    def adjust_peer_score(self, peer_id: str, delta: int, reason: str = '') -> int:
        """Adjust a peer's reputation score.

        Args:
            peer_id: The peer to adjust.
            delta: Score change (positive = reward, negative = penalty).
            reason: Optional reason for logging.

        Returns:
            New score value, or -1 if peer not found.
        """
        if peer_id not in self.connections:
            return -1
        peer = self.connections[peer_id]
        peer.score = max(0, min(100, peer.score + delta))
        if reason:
            logger.debug(f"Peer {peer_id[:12]}... score {'+' if delta >= 0 else ''}{delta} ({reason}) -> {peer.score}")
        return peer.score

    def penalize_peer(self, peer_id: str, severity: int = 10, reason: str = '') -> int:
        """Penalize a peer for misbehavior.

        Args:
            peer_id: The peer to penalize.
            severity: Penalty amount (subtracted from score).
            reason: Reason for the penalty.

        Returns:
            New score value.
        """
        return self.adjust_peer_score(peer_id, -abs(severity), reason or 'penalty')

    def reward_peer(self, peer_id: str, amount: int = 5, reason: str = '') -> int:
        """Reward a peer for good behavior.

        Args:
            peer_id: The peer to reward.
            amount: Reward amount (added to score).
            reason: Reason for the reward.

        Returns:
            New score value.
        """
        return self.adjust_peer_score(peer_id, abs(amount), reason or 'reward')

    async def evict_low_score_peers(self, min_score: int = 20) -> List[str]:
        """Disconnect peers with scores below the threshold.

        Args:
            min_score: Minimum acceptable score (default 20).

        Returns:
            List of evicted peer IDs.
        """
        evicted = []
        for peer_id, peer in list(self.connections.items()):
            if peer.score < min_score:
                logger.warning(
                    f"Evicting peer {peer_id[:12]}... (score={peer.score} < {min_score})"
                )
                await self._disconnect_peer(peer_id)
                evicted.append(peer_id)
        return evicted

    def get_peers_by_score(self, ascending: bool = False) -> list:
        """Get peers sorted by reputation score.

        Args:
            ascending: If True, lowest score first (useful for finding bad peers).

        Returns:
            List of peer dicts sorted by score.
        """
        peers = sorted(
            self.connections.values(),
            key=lambda p: p.score,
            reverse=not ascending,
        )
        return [p.to_dict() for p in peers]

    def get_peer_list(self) -> list:
        """Get list of connected peers"""
        return [peer.to_dict() for peer in self.connections.values()]
    def get_stats(self) -> dict:
        """Get network statistics"""
        return {
            **self.stats,
            'connected_peers': len(self.connections),
            'max_peers': self.max_peers,
            'port': self.port,
            'peer_id': self.peer_id
        }
