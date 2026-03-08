"""L1 ↔ L2 Internal Bridge — moves QBC between UTXO (L1) and QVM accounts (L2).

Deposit:  L1 UTXOs (Dilithium address) → L2 QVM account (EVM/MetaMask address)
Withdraw: L2 QVM account (EVM address) → L1 UTXO (Dilithium address)

Both operations are atomic — handled within a single database transaction.
"""

import hashlib
import json
import time
from decimal import Decimal
from typing import Optional

from sqlalchemy import text as sa_text

from .config import Config
from .utils.logger import get_logger

logger = get_logger(__name__)


class L1L2Bridge:
    """Bridge between L1 (UTXO/Dilithium) and L2 (QVM accounts/EVM)."""

    def __init__(self, db_manager):
        self.db = db_manager

    def deposit(
        self,
        from_address: str,
        to_address: str,
        amount: Decimal,
        public_key_hex: str,
        signature_hex: str,
        utxo_strategy: str = 'largest_first',
    ) -> dict:
        """Deposit QBC from L1 UTXOs into an L2 QVM account.

        Args:
            from_address: L1 Dilithium address (UTXO owner).
            to_address: L2 EVM address (MetaMask, 0x-prefixed or raw hex).
            amount: QBC amount to deposit.
            public_key_hex: Dilithium public key hex (for signature verification).
            signature_hex: Dilithium signature over deposit message.
            utxo_strategy: UTXO selection strategy.

        Returns:
            dict with tx_hash, status, amount, l2_address.
        """
        from .quantum.crypto import DilithiumSigner

        # Validate inputs
        if amount <= 0:
            raise ValueError("Amount must be positive")

        # Verify Dilithium signature proves ownership
        pk = bytes.fromhex(public_key_hex)
        derived_addr = DilithiumSigner.derive_address(pk)
        if derived_addr != from_address:
            raise ValueError("Public key does not match from_address")

        deposit_msg = json.dumps({
            'action': 'l2_deposit',
            'from': from_address,
            'to': to_address,
            'amount': str(amount),
        }, sort_keys=True).encode()
        sig = bytes.fromhex(signature_hex)
        if not DilithiumSigner.verify(pk, deposit_msg, sig):
            raise ValueError("Invalid Dilithium signature")

        # Normalize L2 address (strip 0x prefix)
        l2_addr = to_address.replace('0x', '').lower()

        with self.db.get_session() as session:
            # Select UTXOs with row-level lock
            sort_order = "ASC" if utxo_strategy == 'smallest_first' else "DESC"
            rows = session.execute(
                sa_text(f"""
                    SELECT txid, vout, amount FROM utxos
                    WHERE address = :addr AND spent = false
                    ORDER BY amount {sort_order}
                    FOR UPDATE
                """),
                {'addr': from_address}
            ).fetchall()

            if not rows:
                raise ValueError("No UTXOs available")

            available = sum(Decimal(str(r[2])) for r in rows)
            if available < amount:
                raise ValueError(f"Insufficient L1 balance: have {available}, need {amount}")

            # Select UTXOs
            selected_rows = []
            total = Decimal(0)
            for r in rows:
                selected_rows.append(r)
                total += Decimal(str(r[2]))
                if total >= amount:
                    break

            change = total - amount

            # Deterministic tx hash
            input_nonce = ":".join(f"{r[0]}:{r[1]}" for r in selected_rows)
            tx_hash = hashlib.sha256(
                f"l2_deposit:{from_address}:{l2_addr}:{amount}:{input_nonce}:{time.time()}".encode()
            ).hexdigest()

            # Consume UTXOs
            for r in selected_rows:
                result = session.execute(
                    sa_text("UPDATE utxos SET spent = true, spent_by = :txid WHERE txid = :utxid AND vout = :vout AND spent = false"),
                    {'txid': tx_hash, 'utxid': r[0], 'vout': r[1]}
                )
                if result.rowcount == 0:
                    raise ValueError(f"UTXO already spent: {r[0]}:{r[1]}")

            # Credit L2 account
            session.execute(
                sa_text("""
                    INSERT INTO accounts (address, nonce, balance, code_hash, storage_root)
                    VALUES (:addr, 0, :amt, '', '')
                    ON CONFLICT (address) DO UPDATE SET balance = accounts.balance + :amt
                """),
                {'addr': l2_addr, 'amt': str(amount)}
            )

            # Create change UTXO if needed
            outputs = [{'address': l2_addr, 'amount': str(amount), 'type': 'l2_credit'}]
            vout = 0
            if change > 0:
                session.execute(
                    sa_text("""
                        INSERT INTO utxos (txid, vout, amount, address, proof, block_height, spent)
                        VALUES (:txid, :vout, :amt, :addr, '{}', :h, false)
                    """),
                    {'txid': tx_hash, 'vout': vout, 'amt': str(change),
                     'addr': from_address, 'h': self.db.get_current_height()}
                )
                outputs.append({'address': from_address, 'amount': str(change), 'type': 'change'})
                vout += 1

            # Record transaction
            session.execute(
                sa_text("""
                    INSERT INTO transactions (txid, inputs, outputs, fee, signature, public_key,
                                              timestamp, status, tx_type, to_address, data,
                                              gas_limit, gas_price, nonce)
                    VALUES (:txid, CAST(:inputs AS jsonb), CAST(:outputs AS jsonb), 0, :sig, :pk,
                            :ts, 'confirmed', 'l2_deposit', :to_addr, :data, 0, 0, 0)
                """),
                {
                    'txid': tx_hash,
                    'inputs': json.dumps([{'txid': r[0], 'vout': r[1]} for r in selected_rows]),
                    'outputs': json.dumps(outputs),
                    'sig': signature_hex[:128], 'pk': public_key_hex[:128],
                    'ts': time.time(), 'to_addr': l2_addr,
                    'data': json.dumps({
                        'action': 'l2_deposit',
                        'l1_address': from_address,
                        'l2_address': l2_addr,
                        'amount': str(amount),
                    }),
                }
            )

            # Log the bridge operation
            session.execute(
                sa_text("""
                    INSERT INTO l1l2_bridge_log (txid, direction, l1_address, l2_address, amount, status, block_height)
                    VALUES (:txid, 'deposit', :l1, :l2, :amt, 'confirmed', :h)
                    ON CONFLICT (txid) DO NOTHING
                """),
                {'txid': tx_hash, 'l1': from_address, 'l2': l2_addr,
                 'amt': str(amount), 'h': self.db.get_current_height()}
            )

            session.commit()

        logger.info(f"L2 deposit: {from_address[:8]}→0x{l2_addr[:8]} {amount} QBC")
        return {
            'tx_hash': tx_hash,
            'status': 'confirmed',
            'amount': str(amount),
            'l1_address': from_address,
            'l2_address': '0x' + l2_addr,
            'change': str(change) if change > 0 else '0',
        }

    def withdraw(
        self,
        from_address: str,
        to_address: str,
        amount: Decimal,
    ) -> dict:
        """Withdraw QBC from L2 QVM account to L1 UTXO.

        Args:
            from_address: L2 EVM address (QVM account with balance).
            to_address: L1 Dilithium address to receive UTXOs.
            amount: QBC amount to withdraw.

        Returns:
            dict with tx_hash, status, amount, l1_address.
        """
        if amount <= 0:
            raise ValueError("Amount must be positive")

        l2_addr = from_address.replace('0x', '').lower()

        with self.db.get_session() as session:
            # Check L2 balance with lock
            result = session.execute(
                sa_text("SELECT balance FROM accounts WHERE address = :addr FOR UPDATE"),
                {'addr': l2_addr}
            ).scalar()
            l2_balance = Decimal(str(result)) if result else Decimal(0)

            if l2_balance < amount:
                raise ValueError(f"Insufficient L2 balance: have {l2_balance}, need {amount}")

            # Deterministic tx hash
            tx_hash = hashlib.sha256(
                f"l2_withdraw:{l2_addr}:{to_address}:{amount}:{time.time()}".encode()
            ).hexdigest()

            # Debit L2 account
            session.execute(
                sa_text("UPDATE accounts SET balance = balance - :amt WHERE address = :addr"),
                {'amt': str(amount), 'addr': l2_addr}
            )

            # Create L1 UTXO
            current_height = self.db.get_current_height()
            session.execute(
                sa_text("""
                    INSERT INTO utxos (txid, vout, amount, address, proof, block_height, spent)
                    VALUES (:txid, 0, :amt, :addr, '{}', :h, false)
                """),
                {'txid': tx_hash, 'amt': str(amount), 'addr': to_address, 'h': current_height}
            )

            # Record transaction
            outputs = [{'address': to_address, 'amount': str(amount), 'type': 'l1_utxo'}]
            session.execute(
                sa_text("""
                    INSERT INTO transactions (txid, inputs, outputs, fee, signature, public_key,
                                              timestamp, status, tx_type, to_address, data,
                                              gas_limit, gas_price, nonce)
                    VALUES (:txid, '[]'::jsonb, CAST(:outputs AS jsonb), 0, '', '',
                            :ts, 'confirmed', 'l2_withdraw', :to_addr, :data, 0, 0, 0)
                """),
                {
                    'txid': tx_hash,
                    'outputs': json.dumps(outputs),
                    'ts': time.time(), 'to_addr': to_address,
                    'data': json.dumps({
                        'action': 'l2_withdraw',
                        'l2_address': l2_addr,
                        'l1_address': to_address,
                        'amount': str(amount),
                    }),
                }
            )

            # Log the bridge operation
            session.execute(
                sa_text("""
                    INSERT INTO l1l2_bridge_log (txid, direction, l1_address, l2_address, amount, status, block_height)
                    VALUES (:txid, 'withdraw', :l1, :l2, :amt, 'confirmed', :h)
                    ON CONFLICT (txid) DO NOTHING
                """),
                {'txid': tx_hash, 'l1': to_address, 'l2': l2_addr,
                 'amt': str(amount), 'h': current_height}
            )

            session.commit()

        logger.info(f"L2 withdraw: 0x{l2_addr[:8]}→{to_address[:8]} {amount} QBC")
        return {
            'tx_hash': tx_hash,
            'status': 'confirmed',
            'amount': str(amount),
            'l2_address': '0x' + l2_addr,
            'l1_address': to_address,
        }

    def get_combined_balance(self, address: str) -> dict:
        """Get both L1 and L2 balances for an address.

        Accepts either format — tries both address systems.
        """
        addr = address.replace('0x', '').lower()

        l1_balance = self.db.get_balance(addr)
        l2_balance = self.db.get_account_balance(addr)

        return {
            'address': address,
            'l1_balance': str(l1_balance),
            'l2_balance': str(l2_balance),
            'total': str(l1_balance + l2_balance),
            'l1_utxo_count': self.db.get_utxo_count(addr),
        }

    def get_status(self) -> dict:
        """Get bridge statistics."""
        with self.db.get_session() as session:
            # Total deposits
            dep = session.execute(
                sa_text("SELECT COUNT(*), COALESCE(SUM(amount), 0) FROM l1l2_bridge_log WHERE direction = 'deposit'")
            ).fetchone()
            # Total withdrawals
            wd = session.execute(
                sa_text("SELECT COUNT(*), COALESCE(SUM(amount), 0) FROM l1l2_bridge_log WHERE direction = 'withdraw'")
            ).fetchone()
            # Recent operations
            recent = session.execute(
                sa_text("""
                    SELECT txid, direction, l1_address, l2_address, amount, status, created_at
                    FROM l1l2_bridge_log ORDER BY created_at DESC LIMIT 20
                """)
            ).fetchall()

        return {
            'deposits': {'count': dep[0] if dep else 0, 'total_volume': str(dep[1]) if dep else '0'},
            'withdrawals': {'count': wd[0] if wd else 0, 'total_volume': str(wd[1]) if wd else '0'},
            'recent': [
                {
                    'txid': r[0], 'direction': r[1],
                    'l1_address': r[2], 'l2_address': r[3],
                    'amount': str(r[4]), 'status': r[5],
                    'created_at': str(r[6]) if r[6] else None,
                }
                for r in (recent or [])
            ],
        }
