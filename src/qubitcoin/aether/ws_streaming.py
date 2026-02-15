"""
Aether Tree WebSocket Streaming

Provides real-time streaming of Aether Tree events over WebSocket.
Supports per-session chat streaming, Phi updates, knowledge graph
changes, and consciousness events.

Events streamed:
  - aether_response: Chat response from Aether (per session)
  - phi_update: Phi value change
  - knowledge_node: New knowledge node added
  - consciousness_event: Consciousness threshold crossing
  - circulation_update: QBC circulation metrics change
  - token_transfer: QBC-20/721 transfer detected
"""
import asyncio
import json
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

from ..utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class AetherWSClient:
    """Represents a connected Aether WebSocket client."""
    websocket: object  # WebSocket instance
    session_id: Optional[str] = None
    subscriptions: Set[str] = field(default_factory=lambda: {
        'phi_update', 'consciousness_event', 'knowledge_node',
    })
    connected_at: float = 0.0
    last_activity: float = 0.0
    messages_sent: int = 0


class AetherWSManager:
    """Manages WebSocket connections for Aether Tree streaming.

    Clients connect to /ws/aether with optional session_id and event
    subscriptions. Global events (Phi, consciousness) are broadcast to
    all subscribers. Session-scoped events (aether_response) go only to
    the matching session.
    """

    # Valid event types clients can subscribe to
    VALID_EVENTS = {
        'aether_response',      # Chat responses (session-scoped)
        'phi_update',           # Phi value changes
        'knowledge_node',       # New knowledge nodes
        'consciousness_event',  # Consciousness threshold events
        'circulation_update',   # QBC circulation changes
        'token_transfer',       # QBC-20/721 transfers
    }

    def __init__(self, max_clients: int = 1000) -> None:
        self._clients: Dict[int, AetherWSClient] = {}
        self._max_clients = max_clients
        self._total_events_broadcast: int = 0

    @property
    def client_count(self) -> int:
        """Number of currently connected clients."""
        return len(self._clients)

    def register(self, websocket: object, session_id: Optional[str] = None,
                 subscriptions: Optional[Set[str]] = None) -> int:
        """Register a new WebSocket client.

        Args:
            websocket: The WebSocket connection object.
            session_id: Optional chat session to bind to.
            subscriptions: Set of event types to receive.

        Returns:
            Client ID (used for tracking).
        """
        client_id = id(websocket)

        subs = subscriptions or {
            'phi_update', 'consciousness_event', 'knowledge_node',
        }
        # Filter to valid event types only
        subs = subs & self.VALID_EVENTS

        # Session-scoped events require a session_id
        if session_id:
            subs.add('aether_response')

        self._clients[client_id] = AetherWSClient(
            websocket=websocket,
            session_id=session_id,
            subscriptions=subs,
            connected_at=time.time(),
            last_activity=time.time(),
        )

        # Evict oldest if over capacity
        if len(self._clients) > self._max_clients:
            oldest_id = min(
                self._clients,
                key=lambda k: self._clients[k].connected_at,
            )
            del self._clients[oldest_id]
            logger.info(f"Aether WS: evicted oldest client (capacity {self._max_clients})")

        logger.info(f"Aether WS: client registered (total: {len(self._clients)})")
        return client_id

    def unregister(self, websocket: object) -> None:
        """Remove a disconnected WebSocket client."""
        client_id = id(websocket)
        if client_id in self._clients:
            del self._clients[client_id]
            logger.debug(f"Aether WS: client unregistered (total: {len(self._clients)})")

    async def broadcast(self, event_type: str, data: dict,
                        session_id: Optional[str] = None) -> int:
        """Broadcast an event to subscribed clients.

        Args:
            event_type: Type of event (must be in VALID_EVENTS).
            data: Event data payload.
            session_id: If set, only send aether_response to this session.

        Returns:
            Number of clients the message was sent to.
        """
        if event_type not in self.VALID_EVENTS:
            return 0

        message = json.dumps({
            'type': event_type,
            'data': data,
            'timestamp': time.time(),
        })

        sent_count = 0
        disconnected: List[int] = []

        for client_id, client in self._clients.items():
            # Check subscription
            if event_type not in client.subscriptions:
                continue

            # Session-scoped events: only send to matching session
            if event_type == 'aether_response' and session_id:
                if client.session_id != session_id:
                    continue

            try:
                await client.websocket.send_text(message)
                client.last_activity = time.time()
                client.messages_sent += 1
                sent_count += 1
            except Exception:
                disconnected.append(client_id)

        # Clean up disconnected clients
        for client_id in disconnected:
            if client_id in self._clients:
                del self._clients[client_id]

        self._total_events_broadcast += sent_count
        return sent_count

    def broadcast_sync(self, event_type: str, data: dict,
                       session_id: Optional[str] = None) -> None:
        """Schedule a broadcast from synchronous code.

        Safe to call from non-async contexts. The broadcast is scheduled
        as a fire-and-forget task on the running event loop.
        """
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.ensure_future(
                    self.broadcast(event_type, data, session_id)
                )
            else:
                loop.run_until_complete(
                    self.broadcast(event_type, data, session_id)
                )
        except RuntimeError:
            # No event loop available (e.g., during testing)
            pass

    def get_stats(self) -> dict:
        """Get WebSocket streaming statistics."""
        return {
            'connected_clients': len(self._clients),
            'max_clients': self._max_clients,
            'total_events_broadcast': self._total_events_broadcast,
            'clients': [
                {
                    'session_id': c.session_id,
                    'subscriptions': sorted(c.subscriptions),
                    'connected_at': c.connected_at,
                    'messages_sent': c.messages_sent,
                }
                for c in self._clients.values()
            ],
        }
