"""
UTXO Fee Collector

Handles fee deduction from user UTXOs and creation of fee UTXOs to treasury.
Used by both Aether Tree chat and contract deployment systems.

Fee flow:
  1. Select sufficient UTXOs from payer's address to cover fee
  2. Create a fee transaction: inputs → [fee output to treasury, change output to payer]
  3. Record the fee transaction in the database
  4. Log the collection for auditing
"""
import hashlib
import json
import time
from dataclasses import dataclass, field, asdict
from decimal import Decimal
from typing import List, Optional, Tuple

from ..config import Config
from ..utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class FeeRecord:
    """Immutable record of a fee collection event."""
    fee_txid: str
    payer_address: str
    treasury_address: str
    fee_amount: Decimal
    fee_type: str  # 'aether_chat', 'aether_query', 'contract_deploy', 'contract_execute'
    timestamp: float
    block_height: int
    inputs_consumed: int
    change_amount: Decimal

    def to_dict(self) -> dict:
        d = asdict(self)
        d['fee_amount'] = str(d['fee_amount'])
        d['change_amount'] = str(d['change_amount'])
        return d


class FeeCollector:
    """Collect fees via UTXO spending and route to treasury."""

    def __init__(self, db_manager: object) -> None:
        """
        Args:
            db_manager: DatabaseManager instance with UTXO operations.
        """
        self._db = db_manager
        self._audit_log: List[FeeRecord] = []
        self._max_audit_entries: int = 10000

    def collect_fee(
        self,
        payer_address: str,
        fee_amount: Decimal,
        fee_type: str,
        treasury_address: str = '',
    ) -> Tuple[bool, str, Optional[FeeRecord]]:
        """Deduct a fee from the payer's UTXOs and create a fee UTXO to treasury.

        Args:
            payer_address: Address to deduct fee from.
            fee_amount: Fee amount in QBC.
            fee_type: Type of fee ('aether_chat', 'contract_deploy', etc.).
            treasury_address: Override treasury address (uses config default if empty).

        Returns:
            (success, message, FeeRecord or None)
        """
        if fee_amount <= 0:
            return True, "No fee required", None

        # Resolve treasury address
        if not treasury_address:
            if fee_type.startswith('aether'):
                treasury_address = Config.AETHER_FEE_TREASURY_ADDRESS
            elif fee_type.startswith('contract'):
                treasury_address = Config.CONTRACT_FEE_TREASURY_ADDRESS
            else:
                treasury_address = Config.AETHER_FEE_TREASURY_ADDRESS

        if not treasury_address:
            logger.warning(f"No treasury address configured for {fee_type}, fee skipped")
            return True, "No treasury address configured, fee skipped", None

        if payer_address == treasury_address:
            return True, "Payer is treasury, fee skipped", None

        # Check balance
        balance = self._db.get_balance(payer_address)
        if balance < fee_amount:
            return False, f"Insufficient balance: {balance} < {fee_amount} QBC", None

        # Select UTXOs to cover the fee
        utxos = self._db.get_utxos(payer_address)
        if not utxos:
            return False, "No UTXOs available", None

        selected, total_input = self._select_utxos(utxos, fee_amount)
        if total_input < fee_amount:
            return False, f"Could not select sufficient UTXOs: {total_input} < {fee_amount}", None

        change_amount = total_input - fee_amount
        block_height = self._db.get_current_height()

        # Build fee transaction
        fee_txid = self._compute_fee_txid(payer_address, treasury_address,
                                           fee_amount, fee_type)

        inputs = [{'txid': u.txid, 'vout': u.vout} for u in selected]
        outputs = [{'address': treasury_address, 'amount': fee_amount}]
        if change_amount > 0:
            outputs.append({'address': payer_address, 'amount': change_amount})

        # Execute the UTXO transfer in a single database session
        try:
            with self._db.get_session() as session:
                # Mark input UTXOs as spent
                self._db.mark_utxos_spent(inputs, fee_txid, session)

                # Create output UTXOs
                self._db.create_utxos(
                    fee_txid, outputs, block_height,
                    proof={'fee_type': fee_type}, session=session
                )

                # Store the fee transaction record
                from sqlalchemy import text
                session.execute(
                    text("""
                        INSERT INTO transactions
                        (txid, inputs, outputs, fee, signature, public_key,
                         timestamp, block_height, status, tx_type)
                        VALUES (:txid, CAST(:inputs AS jsonb), CAST(:outputs AS jsonb),
                                :fee, :sig, :pk, :ts, :height, 'confirmed', 'fee')
                    """),
                    {
                        'txid': fee_txid,
                        'inputs': json.dumps(inputs),
                        'outputs': json.dumps([
                            {'address': o['address'], 'amount': str(o['amount'])}
                            for o in outputs
                        ]),
                        'fee': str(fee_amount),
                        'sig': '',
                        'pk': '',
                        'ts': time.time(),
                        'height': block_height,
                    }
                )

                session.commit()

        except Exception as e:
            logger.error(f"Fee collection failed: {e}")
            return False, f"Fee transaction failed: {e}", None

        # Create audit record
        record = FeeRecord(
            fee_txid=fee_txid,
            payer_address=payer_address,
            treasury_address=treasury_address,
            fee_amount=fee_amount,
            fee_type=fee_type,
            timestamp=time.time(),
            block_height=block_height,
            inputs_consumed=len(selected),
            change_amount=change_amount,
        )
        self._add_audit_record(record)

        logger.info(
            f"Fee collected: {fee_amount} QBC ({fee_type}) "
            f"from {payer_address[:16]}... -> {treasury_address[:16]}..."
        )
        return True, "Fee collected", record

    def _select_utxos(
        self, utxos: list, target: Decimal,
        strategy: str = 'largest_first',
    ) -> Tuple[list, Decimal]:
        """Select UTXOs to cover the target amount.

        Strategies:
        - ``largest_first``: Fewest inputs (default prior behavior).
        - ``smallest_first``: Consolidates dust UTXOs.
        - ``exact_match``: Tries to find a single UTXO that exactly covers
          the target (no change output needed). Falls back to smallest_first.

        Args:
            utxos: Available unspent outputs.
            target: Amount needed.
            strategy: Selection strategy name.

        Returns:
            (selected_utxos, total_input_amount)
        """
        if strategy == 'exact_match':
            # Try to find a UTXO that exactly matches the target
            for utxo in utxos:
                if utxo.amount == target:
                    return [utxo], utxo.amount
            # Fall back to smallest_first
            strategy = 'smallest_first'

        if strategy == 'smallest_first':
            sorted_utxos = sorted(utxos, key=lambda u: u.amount)
        else:  # largest_first
            sorted_utxos = sorted(utxos, key=lambda u: u.amount, reverse=True)

        selected = []
        total = Decimal(0)
        for utxo in sorted_utxos:
            if total >= target:
                break
            selected.append(utxo)
            total += utxo.amount

        return selected, total

    def _compute_fee_txid(self, payer: str, treasury: str,
                          amount: Decimal, fee_type: str) -> str:
        """Compute a deterministic transaction ID for a fee transaction."""
        data = {
            'payer': payer,
            'treasury': treasury,
            'amount': str(amount),
            'fee_type': fee_type,
            'timestamp': time.time(),
        }
        return hashlib.sha256(
            json.dumps(data, sort_keys=True).encode()
        ).hexdigest()

    def _add_audit_record(self, record: FeeRecord) -> None:
        """Add a record to the in-memory audit log."""
        self._audit_log.append(record)
        # Evict oldest if over capacity
        if len(self._audit_log) > self._max_audit_entries:
            self._audit_log = self._audit_log[-self._max_audit_entries:]

    def get_stats(self) -> dict:
        """Aggregate fee collection statistics."""
        total = self.get_total_fees_collected()
        by_type = {}
        for fee_type in ('aether_chat', 'aether_query', 'contract_deploy', 'contract_execute'):
            by_type[fee_type] = str(self.get_total_fees_collected(fee_type))
        return {
            'total_collected': str(total),
            'total_events': len(self._audit_log),
            'by_type': by_type,
            'recent': self.get_audit_log(limit=10),
        }

    def get_audit_log(self, limit: int = 100, fee_type: Optional[str] = None) -> List[dict]:
        """Get recent fee audit records.

        Args:
            limit: Maximum records to return.
            fee_type: Filter by fee type (optional).

        Returns:
            List of fee record dicts, most recent first.
        """
        records = self._audit_log
        if fee_type:
            records = [r for r in records if r.fee_type == fee_type]
        return [r.to_dict() for r in records[-limit:][::-1]]

    def get_total_fees_collected(self, fee_type: Optional[str] = None) -> Decimal:
        """Get total fees collected (from in-memory audit log).

        Args:
            fee_type: Filter by fee type (optional).

        Returns:
            Total QBC collected.
        """
        records = self._audit_log
        if fee_type:
            records = [r for r in records if r.fee_type == fee_type]
        return sum((r.fee_amount for r in records), Decimal(0))
