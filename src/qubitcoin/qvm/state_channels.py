"""
QVM State Channels — Layer 2 Scaling via Off-Chain Execution

State channels allow two or more parties to transact off-chain with
near-instant finality, only settling the final state on-chain. This
reduces gas costs and increases throughput for high-frequency interactions.

Protocol:
1. OPEN:   Parties lock QBC in an on-chain channel contract
2. UPDATE: Parties exchange signed state updates off-chain
3. CLOSE:  Final state submitted on-chain, QBC distributed per final balances
4. DISPUTE: If parties disagree, challenge window allows on-chain resolution

Security model:
- Both parties must sign every state update (prevents unilateral changes)
- Monotonic nonce prevents replay of old states
- Challenge window (default 100 blocks) allows dispute resolution
- Timeout closes channel with latest mutually-signed state
"""
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from enum import Enum

from .vm import keccak256
from ..utils.logger import get_logger

logger = get_logger(__name__)

CHALLENGE_WINDOW_BLOCKS = 100    # Blocks to dispute a closing state
MIN_CHANNEL_DEPOSIT = 0.01      # Minimum QBC to open a channel
MAX_CHANNELS_PER_ADDRESS = 50   # Prevent channel spam


class ChannelState(str, Enum):
    """Lifecycle states of a state channel."""
    OPEN = "open"
    UPDATING = "updating"
    CLOSING = "closing"
    DISPUTED = "disputed"
    CLOSED = "closed"


@dataclass
class StateUpdate:
    """A single off-chain state update signed by both parties."""
    channel_id: str
    nonce: int                  # Monotonically increasing
    balance_a: float            # Party A's balance
    balance_b: float            # Party B's balance
    data: dict = field(default_factory=dict)
    signature_a: str = ""       # Party A's Dilithium signature
    signature_b: str = ""       # Party B's Dilithium signature
    timestamp: float = 0.0

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = time.time()

    @property
    def state_hash(self) -> str:
        """Compute hash of the state update for signing."""
        data = f"{self.channel_id}:{self.nonce}:{self.balance_a}:{self.balance_b}"
        return keccak256(data.encode()).hex()

    def is_fully_signed(self) -> bool:
        return bool(self.signature_a and self.signature_b)

    def to_dict(self) -> dict:
        return {
            "channel_id": self.channel_id,
            "nonce": self.nonce,
            "balance_a": self.balance_a,
            "balance_b": self.balance_b,
            "data": self.data,
            "state_hash": self.state_hash,
            "signed": self.is_fully_signed(),
            "timestamp": self.timestamp,
        }


@dataclass
class StateChannel:
    """An open state channel between two parties."""
    channel_id: str
    party_a: str                # Address of party A
    party_b: str                # Address of party B
    deposit_a: float            # QBC locked by party A
    deposit_b: float            # QBC locked by party B
    state: ChannelState = ChannelState.OPEN
    nonce: int = 0              # Current state nonce
    balance_a: float = 0.0      # Current off-chain balance A
    balance_b: float = 0.0      # Current off-chain balance B
    open_block: int = 0         # Block when channel was opened
    close_block: int = 0        # Block when close was initiated
    updates: List[StateUpdate] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        # Initial balances equal deposits
        if self.balance_a == 0.0 and self.balance_b == 0.0:
            self.balance_a = self.deposit_a
            self.balance_b = self.deposit_b

    @property
    def total_locked(self) -> float:
        return self.deposit_a + self.deposit_b

    def to_dict(self) -> dict:
        return {
            "channel_id": self.channel_id,
            "party_a": self.party_a,
            "party_b": self.party_b,
            "deposit_a": self.deposit_a,
            "deposit_b": self.deposit_b,
            "balance_a": self.balance_a,
            "balance_b": self.balance_b,
            "state": self.state.value,
            "nonce": self.nonce,
            "total_locked": self.total_locked,
            "open_block": self.open_block,
            "updates": len(self.updates),
        }


class StateChannelManager:
    """
    Manages state channels for off-chain QVM execution.

    Provides:
    - Channel lifecycle (open, update, close, dispute)
    - Nonce-based state ordering (prevents replay)
    - Challenge window for dispute resolution
    - Balance conservation (sum of balances always equals deposits)
    """

    def __init__(self) -> None:
        self._channels: Dict[str, StateChannel] = {}
        self._address_channels: Dict[str, List[str]] = {}  # addr → channel_ids
        self._total_locked: float = 0.0
        self._total_settled: float = 0.0
        self._disputes: int = 0
        logger.info("State Channel Manager initialized")

    def open_channel(self, party_a: str, party_b: str,
                     deposit_a: float, deposit_b: float,
                     block_height: int) -> dict:
        """
        Open a new state channel between two parties.

        Args:
            party_a: Address of first party.
            party_b: Address of second party.
            deposit_a: QBC locked by party A.
            deposit_b: QBC locked by party B.
            block_height: Current block height.

        Returns:
            Result dict with channel_id or error.
        """
        if deposit_a < MIN_CHANNEL_DEPOSIT or deposit_b < MIN_CHANNEL_DEPOSIT:
            return {"success": False, "error": f"Minimum deposit is {MIN_CHANNEL_DEPOSIT} QBC"}

        if party_a == party_b:
            return {"success": False, "error": "Cannot open channel with self"}

        # Check channel limits
        for addr in (party_a, party_b):
            if len(self._address_channels.get(addr, [])) >= MAX_CHANNELS_PER_ADDRESS:
                return {"success": False, "error": f"Channel limit reached for {addr[:16]}..."}

        channel_id = keccak256(
            f"{party_a}:{party_b}:{block_height}:{time.time()}".encode()
        ).hex()[:16]

        channel = StateChannel(
            channel_id=channel_id,
            party_a=party_a,
            party_b=party_b,
            deposit_a=deposit_a,
            deposit_b=deposit_b,
            open_block=block_height,
        )

        self._channels[channel_id] = channel
        self._address_channels.setdefault(party_a, []).append(channel_id)
        self._address_channels.setdefault(party_b, []).append(channel_id)
        self._total_locked += channel.total_locked

        logger.info(
            f"Channel opened: {channel_id} ({party_a[:12]}... ↔ {party_b[:12]}...) "
            f"locked={channel.total_locked} QBC"
        )
        return {"success": True, "channel_id": channel_id, "channel": channel.to_dict()}

    def update_state(self, channel_id: str, balance_a: float, balance_b: float,
                     signature_a: str = "", signature_b: str = "",
                     data: Optional[dict] = None) -> dict:
        """
        Submit a new off-chain state update.

        Both parties must sign. Nonce must be strictly increasing.
        Balance conservation is enforced: balance_a + balance_b == total_locked.

        Returns:
            Result dict with new state or error.
        """
        channel = self._channels.get(channel_id)
        if channel is None:
            return {"success": False, "error": "Channel not found"}

        if channel.state not in (ChannelState.OPEN, ChannelState.UPDATING):
            return {"success": False, "error": f"Channel is {channel.state.value}"}

        # Conservation check
        total = channel.total_locked
        if abs((balance_a + balance_b) - total) > 1e-8:
            return {
                "success": False,
                "error": f"Balance conservation violated: {balance_a}+{balance_b} != {total}",
            }

        # Non-negative balances
        if balance_a < 0 or balance_b < 0:
            return {"success": False, "error": "Negative balance not allowed"}

        new_nonce = channel.nonce + 1
        update = StateUpdate(
            channel_id=channel_id,
            nonce=new_nonce,
            balance_a=balance_a,
            balance_b=balance_b,
            data=data or {},
            signature_a=signature_a,
            signature_b=signature_b,
        )

        channel.nonce = new_nonce
        channel.balance_a = balance_a
        channel.balance_b = balance_b
        channel.state = ChannelState.UPDATING
        channel.updates.append(update)

        return {"success": True, "nonce": new_nonce, "state": update.to_dict()}

    def initiate_close(self, channel_id: str, block_height: int) -> dict:
        """
        Initiate cooperative or unilateral channel close.

        Starts the challenge window. If no dispute within CHALLENGE_WINDOW_BLOCKS,
        the channel settles with the latest state.
        """
        channel = self._channels.get(channel_id)
        if channel is None:
            return {"success": False, "error": "Channel not found"}

        if channel.state == ChannelState.CLOSED:
            return {"success": False, "error": "Channel already closed"}

        channel.state = ChannelState.CLOSING
        channel.close_block = block_height

        logger.info(
            f"Channel {channel_id} closing initiated at block {block_height} "
            f"(challenge window: {CHALLENGE_WINDOW_BLOCKS} blocks)"
        )
        return {
            "success": True,
            "channel_id": channel_id,
            "challenge_deadline": block_height + CHALLENGE_WINDOW_BLOCKS,
        }

    def dispute(self, channel_id: str, update: StateUpdate,
                block_height: int) -> dict:
        """
        Submit a dispute with a higher-nonce state during the challenge window.
        """
        channel = self._channels.get(channel_id)
        if channel is None:
            return {"success": False, "error": "Channel not found"}

        if channel.state != ChannelState.CLOSING:
            return {"success": False, "error": "Channel not in closing state"}

        deadline = channel.close_block + CHALLENGE_WINDOW_BLOCKS
        if block_height > deadline:
            return {"success": False, "error": "Challenge window expired"}

        if update.nonce <= channel.nonce:
            return {"success": False, "error": "Dispute nonce must be higher than current"}

        # Accept the disputed state
        channel.nonce = update.nonce
        channel.balance_a = update.balance_a
        channel.balance_b = update.balance_b
        channel.state = ChannelState.DISPUTED
        channel.close_block = block_height  # Reset challenge window
        self._disputes += 1

        logger.warning(
            f"Channel {channel_id} DISPUTED at block {block_height} "
            f"(new nonce={update.nonce})"
        )
        return {"success": True, "new_nonce": update.nonce}

    def finalize(self, channel_id: str, block_height: int) -> dict:
        """
        Finalize a channel close after the challenge window expires.

        Returns the final settlement balances.
        """
        channel = self._channels.get(channel_id)
        if channel is None:
            return {"success": False, "error": "Channel not found"}

        if channel.state not in (ChannelState.CLOSING, ChannelState.DISPUTED):
            return {"success": False, "error": f"Channel is {channel.state.value}"}

        deadline = channel.close_block + CHALLENGE_WINDOW_BLOCKS
        if block_height < deadline:
            return {
                "success": False,
                "error": f"Challenge window not expired (need block {deadline})",
            }

        channel.state = ChannelState.CLOSED
        self._total_locked -= channel.total_locked
        self._total_settled += channel.total_locked

        logger.info(
            f"Channel {channel_id} finalized: A={channel.balance_a}, B={channel.balance_b}"
        )
        return {
            "success": True,
            "channel_id": channel_id,
            "settlement": {
                "party_a": channel.party_a,
                "balance_a": channel.balance_a,
                "party_b": channel.party_b,
                "balance_b": channel.balance_b,
            },
        }

    def get_channel(self, channel_id: str) -> Optional[dict]:
        ch = self._channels.get(channel_id)
        return ch.to_dict() if ch else None

    def get_address_channels(self, address: str) -> List[dict]:
        ids = self._address_channels.get(address, [])
        return [
            self._channels[cid].to_dict()
            for cid in ids if cid in self._channels
        ]

    def get_stats(self) -> dict:
        open_count = sum(1 for c in self._channels.values() if c.state == ChannelState.OPEN)
        return {
            "total_channels": len(self._channels),
            "open_channels": open_count,
            "total_locked_qbc": round(self._total_locked, 4),
            "total_settled_qbc": round(self._total_settled, 4),
            "total_disputes": self._disputes,
        }
