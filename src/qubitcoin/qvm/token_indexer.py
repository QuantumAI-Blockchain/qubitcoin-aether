"""
QBC Token Indexer

Indexes QBC-20 (fungible) and QBC-721 (non-fungible) token transfers
by parsing event logs from QVM contract executions.

Tracks:
  - Token transfers (from, to, amount/tokenId)
  - Token holder balances
  - Token metadata (name, symbol, decimals, total supply)
  - Transfer history per address
"""
import hashlib
import time
from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, List, Optional

from ..utils.logger import get_logger

logger = get_logger(__name__)

# EVM event topic signatures (keccak256 of event signature string)
# Transfer(address,address,uint256) — shared by QBC-20 and QBC-721
TRANSFER_TOPIC = hashlib.sha3_256(
    b'Transfer(address,address,uint256)'
).hexdigest()

# Approval(address,address,uint256)
APPROVAL_TOPIC = hashlib.sha3_256(
    b'Approval(address,address,uint256)'
).hexdigest()

ZERO_ADDRESS = '0x' + '0' * 40


@dataclass
class TokenTransfer:
    """A single token transfer event."""
    token_address: str
    tx_hash: str
    block_height: int
    from_address: str
    to_address: str
    amount: Decimal  # For QBC-20: token amount; for QBC-721: tokenId
    token_standard: str  # 'QBC-20' or 'QBC-721'
    timestamp: float = 0.0
    log_index: int = 0

    def to_dict(self) -> dict:
        return {
            'token_address': self.token_address,
            'tx_hash': self.tx_hash,
            'block_height': self.block_height,
            'from_address': self.from_address,
            'to_address': self.to_address,
            'amount': str(self.amount),
            'token_standard': self.token_standard,
            'timestamp': self.timestamp,
            'log_index': self.log_index,
        }


@dataclass
class TokenInfo:
    """Metadata about a tracked token contract."""
    contract_address: str
    token_standard: str  # 'QBC-20' or 'QBC-721'
    name: str = ''
    symbol: str = ''
    decimals: int = 18
    total_supply: Decimal = Decimal('0')
    total_transfers: int = 0
    total_holders: int = 0
    first_seen_block: int = 0

    def to_dict(self) -> dict:
        return {
            'contract_address': self.contract_address,
            'token_standard': self.token_standard,
            'name': self.name,
            'symbol': self.symbol,
            'decimals': self.decimals,
            'total_supply': str(self.total_supply),
            'total_transfers': self.total_transfers,
            'total_holders': self.total_holders,
            'first_seen_block': self.first_seen_block,
        }


class TokenIndexer:
    """Index QBC-20 and QBC-721 token transfers from contract event logs.

    Parses Transfer events from transaction receipt logs and maintains
    an in-memory index of balances, holders, and transfer history.
    Production systems should persist this to CockroachDB.
    """

    def __init__(self, max_transfers: int = 100000) -> None:
        """
        Args:
            max_transfers: Maximum number of transfers to keep in memory.
        """
        # token_address -> TokenInfo
        self._tokens: Dict[str, TokenInfo] = {}
        # token_address -> holder_address -> balance
        self._balances: Dict[str, Dict[str, Decimal]] = {}
        # All transfers (most recent kept)
        self._transfers: List[TokenTransfer] = []
        self._max_transfers = max_transfers
        # Known token standards by contract address
        self._known_standards: Dict[str, str] = {}

    def register_token(self, contract_address: str, token_standard: str,
                       name: str = '', symbol: str = '', decimals: int = 18,
                       total_supply: Decimal = Decimal('0'),
                       first_seen_block: int = 0) -> TokenInfo:
        """Register a token contract for tracking.

        Args:
            contract_address: The token contract address.
            token_standard: 'QBC-20' or 'QBC-721'.
            name: Token name.
            symbol: Token symbol.
            decimals: Decimal places (QBC-20 only).
            total_supply: Initial total supply.
            first_seen_block: Block where token was first deployed.

        Returns:
            TokenInfo for the registered token.
        """
        addr = contract_address.lower()
        info = TokenInfo(
            contract_address=addr,
            token_standard=token_standard,
            name=name,
            symbol=symbol,
            decimals=decimals,
            total_supply=total_supply,
            first_seen_block=first_seen_block,
        )
        self._tokens[addr] = info
        self._known_standards[addr] = token_standard
        if addr not in self._balances:
            self._balances[addr] = {}

        logger.info(f"Token registered: {symbol} ({token_standard}) at {addr[:10]}...")
        return info

    def process_receipt_logs(self, tx_hash: str, block_height: int,
                            logs: List[dict],
                            timestamp: float = 0.0) -> List[TokenTransfer]:
        """Process event logs from a transaction receipt to detect transfers.

        Args:
            tx_hash: Transaction hash.
            block_height: Block height of the transaction.
            logs: List of log entries from the transaction receipt.
            timestamp: Block timestamp.

        Returns:
            List of detected token transfers.
        """
        transfers: List[TokenTransfer] = []

        for log_index, log_entry in enumerate(logs):
            transfer = self._parse_transfer_log(
                log_entry, tx_hash, block_height, log_index, timestamp,
            )
            if transfer:
                transfers.append(transfer)
                self._record_transfer(transfer)

        return transfers

    def _parse_transfer_log(self, log_entry: dict, tx_hash: str,
                            block_height: int, log_index: int,
                            timestamp: float) -> Optional[TokenTransfer]:
        """Parse a single log entry for Transfer events."""
        topics = log_entry.get('topics', [])
        if not topics:
            return None

        # Check if this is a Transfer event
        topic0 = topics[0].lower() if isinstance(topics[0], str) else ''
        # Strip 0x prefix for comparison
        topic0_clean = topic0.replace('0x', '')

        if topic0_clean != TRANSFER_TOPIC:
            return None

        # Need at least 3 topics for Transfer(from, to, value/tokenId)
        if len(topics) < 3:
            return None

        contract_address = log_entry.get('address', '').lower()
        from_address = _decode_address_topic(topics[1])
        to_address = _decode_address_topic(topics[2])

        # Determine amount from data field
        data = log_entry.get('data', '0x0')
        amount = _decode_uint256(data)

        # Determine token standard
        standard = self._known_standards.get(contract_address, 'QBC-20')

        return TokenTransfer(
            token_address=contract_address,
            tx_hash=tx_hash,
            block_height=block_height,
            from_address=from_address,
            to_address=to_address,
            amount=amount,
            token_standard=standard,
            timestamp=timestamp or time.time(),
            log_index=log_index,
        )

    def _record_transfer(self, transfer: TokenTransfer) -> None:
        """Record a transfer and update balances."""
        addr = transfer.token_address

        # Auto-register unknown tokens
        if addr not in self._tokens:
            self.register_token(
                addr, transfer.token_standard,
                first_seen_block=transfer.block_height,
            )

        token = self._tokens[addr]
        token.total_transfers += 1

        # Initialize balance dict if needed
        if addr not in self._balances:
            self._balances[addr] = {}

        balances = self._balances[addr]

        # Deduct from sender (unless mint from zero address)
        if transfer.from_address != ZERO_ADDRESS:
            old_bal = balances.get(transfer.from_address, Decimal('0'))
            new_bal = max(Decimal('0'), old_bal - transfer.amount)
            if new_bal > 0:
                balances[transfer.from_address] = new_bal
            elif transfer.from_address in balances:
                del balances[transfer.from_address]

        # Add to receiver (unless burn to zero address)
        if transfer.to_address != ZERO_ADDRESS:
            balances[transfer.to_address] = (
                balances.get(transfer.to_address, Decimal('0'))
                + transfer.amount
            )

        # Update holder count
        token.total_holders = len(balances)

        # Handle mint (from zero) and burn (to zero)
        if transfer.from_address == ZERO_ADDRESS:
            token.total_supply += transfer.amount
        if transfer.to_address == ZERO_ADDRESS:
            token.total_supply -= transfer.amount

        # Store transfer
        self._transfers.append(transfer)
        if len(self._transfers) > self._max_transfers:
            self._transfers = self._transfers[-self._max_transfers:]

    def get_token_info(self, contract_address: str) -> Optional[dict]:
        """Get metadata about a tracked token."""
        addr = contract_address.lower()
        token = self._tokens.get(addr)
        return token.to_dict() if token else None

    def get_token_balance(self, contract_address: str,
                          holder_address: str) -> Decimal:
        """Get a holder's balance for a specific token."""
        addr = contract_address.lower()
        holder = holder_address.lower()
        return self._balances.get(addr, {}).get(holder, Decimal('0'))

    def get_token_holders(self, contract_address: str,
                          limit: int = 100) -> List[dict]:
        """Get top holders for a token, sorted by balance descending."""
        addr = contract_address.lower()
        balances = self._balances.get(addr, {})
        sorted_holders = sorted(
            balances.items(), key=lambda x: x[1], reverse=True,
        )[:limit]
        return [
            {'address': h, 'balance': str(b)}
            for h, b in sorted_holders
        ]

    def get_transfers(self, contract_address: Optional[str] = None,
                      address: Optional[str] = None,
                      limit: int = 100) -> List[dict]:
        """Get recent token transfers, optionally filtered.

        Args:
            contract_address: Filter by token contract.
            address: Filter by sender or receiver address.
            limit: Maximum number of results.

        Returns:
            List of transfer dicts, newest first.
        """
        results = self._transfers

        if contract_address:
            ca = contract_address.lower()
            results = [t for t in results if t.token_address == ca]

        if address:
            a = address.lower()
            results = [
                t for t in results
                if t.from_address == a or t.to_address == a
            ]

        return [t.to_dict() for t in reversed(results[-limit:])]

    def get_all_tokens(self) -> List[dict]:
        """Get info about all tracked tokens."""
        return [t.to_dict() for t in self._tokens.values()]

    def get_stats(self) -> dict:
        """Get overall indexer statistics."""
        return {
            'tracked_tokens': len(self._tokens),
            'total_transfers': len(self._transfers),
            'total_unique_holders': sum(
                len(b) for b in self._balances.values()
            ),
        }


def _decode_address_topic(topic: object) -> str:
    """Decode an address from a log topic (right-aligned 32 bytes)."""
    if isinstance(topic, str):
        clean = topic.replace('0x', '').lower()
        # Address is last 40 chars of 64-char topic
        if len(clean) >= 40:
            return '0x' + clean[-40:]
        return '0x' + clean.zfill(40)
    return ZERO_ADDRESS


def _decode_uint256(data: object) -> Decimal:
    """Decode a uint256 from hex data."""
    if isinstance(data, str):
        clean = data.replace('0x', '')
        if clean:
            try:
                return Decimal(int(clean, 16))
            except (ValueError, Exception):
                return Decimal('0')
    if isinstance(data, (int, float)):
        return Decimal(str(data))
    return Decimal('0')
