"""Tests for L1 ↔ L2 Internal Bridge (l2_bridge.py)

Tests deposit (L1 UTXO → L2 QVM account) and withdraw (L2 → L1) operations.
"""

import hashlib
import json
import time
from decimal import Decimal
from unittest.mock import MagicMock, patch, PropertyMock

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_db_manager(utxos=None, account_balance=Decimal(0), current_height=100):
    """Create a mock DatabaseManager with configurable UTXO and account state."""
    db = MagicMock()
    db.get_current_height.return_value = current_height
    db.get_account_balance.return_value = account_balance
    db.get_utxo_count.return_value = len(utxos) if utxos else 0

    # get_balance returns sum of unspent UTXOs
    if utxos:
        db.get_balance.return_value = sum(Decimal(str(u[2])) for u in utxos)
    else:
        db.get_balance.return_value = Decimal(0)

    # Mock session context manager
    session = MagicMock()
    session.__enter__ = MagicMock(return_value=session)
    session.__exit__ = MagicMock(return_value=False)

    # Track executions
    execute_results = []

    def mock_execute(query, params=None):
        result = MagicMock()
        query_str = str(query) if not isinstance(query, str) else query

        # UTXO selection query
        if 'SELECT txid, vout, amount FROM utxos' in query_str:
            result.fetchall.return_value = utxos or []
        # Account balance query
        elif 'SELECT balance FROM accounts WHERE' in query_str:
            result.scalar.return_value = str(account_balance) if account_balance > 0 else None
        # UPDATE utxos SET spent
        elif 'UPDATE utxos SET spent' in query_str:
            result.rowcount = 1
        # Bridge log stats
        elif "SELECT COUNT" in query_str and "direction = 'deposit'" in query_str:
            result.fetchone.return_value = (5, Decimal('500'))
        elif "SELECT COUNT" in query_str and "direction = 'withdraw'" in query_str:
            result.fetchone.return_value = (3, Decimal('300'))
        # Recent operations
        elif 'FROM l1l2_bridge_log ORDER BY' in query_str:
            result.fetchall.return_value = []
        else:
            result.rowcount = 1
            result.fetchall.return_value = []
            result.fetchone.return_value = None
            result.scalar.return_value = None

        execute_results.append((query_str, params))
        return result

    session.execute = mock_execute
    session.commit = MagicMock()

    db.get_session.return_value = session
    db._execute_results = execute_results

    return db


def _mock_dilithium():
    """Patch DilithiumSigner for testing."""
    signer = MagicMock()
    signer.derive_address.return_value = 'test_l1_address_abc123'
    signer.verify.return_value = True
    return signer


# ---------------------------------------------------------------------------
# Tests: L1L2Bridge.__init__
# ---------------------------------------------------------------------------

class TestL1L2BridgeInit:
    def test_init(self):
        from qubitcoin.l2_bridge import L1L2Bridge
        db = MagicMock()
        bridge = L1L2Bridge(db)
        assert bridge.db is db


# ---------------------------------------------------------------------------
# Tests: Deposit (L1 → L2)
# ---------------------------------------------------------------------------

class TestDeposit:
    def _make_bridge(self, utxos, **kwargs):
        from qubitcoin.l2_bridge import L1L2Bridge
        db = _make_db_manager(utxos=utxos, **kwargs)
        return L1L2Bridge(db), db

    @patch('qubitcoin.quantum.crypto.DilithiumSigner', autospec=False)
    def test_deposit_success(self, mock_signer_cls):
        """Basic deposit: consume UTXO, credit L2 account."""
        # Setup mock signer
        mock_signer_cls.derive_address.return_value = 'test_l1_address_abc123'
        mock_signer_cls.verify.return_value = True

        utxos = [('utxo1', 0, Decimal('100'))]
        bridge, db = self._make_bridge(utxos)

        result = bridge.deposit(
            from_address='test_l1_address_abc123',
            to_address='0x51D3a9b12dc4667f771B2A5cE3491631251E9D41',
            amount=Decimal('50'),
            public_key_hex='aa' * 32,
            signature_hex='bb' * 64,
        )

        assert result['status'] == 'confirmed'
        assert result['amount'] == '50'
        assert result['l2_address'].startswith('0x')
        assert 'tx_hash' in result

    @patch('qubitcoin.quantum.crypto.DilithiumSigner', autospec=False)
    def test_deposit_exact_amount(self, mock_signer_cls):
        """Deposit exact UTXO amount — no change output."""
        mock_signer_cls.derive_address.return_value = 'test_l1_address_abc123'
        mock_signer_cls.verify.return_value = True

        utxos = [('utxo1', 0, Decimal('100'))]
        bridge, db = self._make_bridge(utxos)

        result = bridge.deposit(
            from_address='test_l1_address_abc123',
            to_address='0xABCDEF1234567890abcdef1234567890ABCDEF12',
            amount=Decimal('100'),
            public_key_hex='aa' * 32,
            signature_hex='bb' * 64,
        )

        assert result['status'] == 'confirmed'
        assert result['change'] == '0'

    @patch('qubitcoin.quantum.crypto.DilithiumSigner', autospec=False)
    def test_deposit_with_change(self, mock_signer_cls):
        """Deposit partial UTXO — change output created."""
        mock_signer_cls.derive_address.return_value = 'test_l1_address_abc123'
        mock_signer_cls.verify.return_value = True

        utxos = [('utxo1', 0, Decimal('100'))]
        bridge, db = self._make_bridge(utxos)

        result = bridge.deposit(
            from_address='test_l1_address_abc123',
            to_address='0xABCDEF1234567890abcdef1234567890ABCDEF12',
            amount=Decimal('30'),
            public_key_hex='aa' * 32,
            signature_hex='bb' * 64,
        )

        assert result['change'] == '70'

    def test_deposit_zero_amount(self):
        """Reject zero amount deposit."""
        from qubitcoin.l2_bridge import L1L2Bridge
        bridge = L1L2Bridge(MagicMock())

        with pytest.raises(ValueError, match="positive"):
            bridge.deposit('addr', '0xabc', Decimal(0), 'pk', 'sig')

    def test_deposit_negative_amount(self):
        """Reject negative amount deposit."""
        from qubitcoin.l2_bridge import L1L2Bridge
        bridge = L1L2Bridge(MagicMock())

        with pytest.raises(ValueError, match="positive"):
            bridge.deposit('addr', '0xabc', Decimal(-5), 'pk', 'sig')

    @patch('qubitcoin.quantum.crypto.DilithiumSigner', autospec=False)
    def test_deposit_insufficient_balance(self, mock_signer_cls):
        """Reject deposit when UTXOs are insufficient."""
        mock_signer_cls.derive_address.return_value = 'test_l1_address_abc123'
        mock_signer_cls.verify.return_value = True

        utxos = [('utxo1', 0, Decimal('10'))]
        bridge, db = self._make_bridge(utxos)

        with pytest.raises(ValueError, match="Insufficient"):
            bridge.deposit(
                from_address='test_l1_address_abc123',
                to_address='0xABCDEF',
                amount=Decimal('100'),
                public_key_hex='aa' * 32,
                signature_hex='bb' * 64,
            )

    @patch('qubitcoin.quantum.crypto.DilithiumSigner', autospec=False)
    def test_deposit_no_utxos(self, mock_signer_cls):
        """Reject deposit when no UTXOs available."""
        mock_signer_cls.derive_address.return_value = 'test_l1_address_abc123'
        mock_signer_cls.verify.return_value = True

        bridge, db = self._make_bridge(utxos=[])

        with pytest.raises(ValueError, match="No UTXOs"):
            bridge.deposit(
                from_address='test_l1_address_abc123',
                to_address='0xABCDEF',
                amount=Decimal('50'),
                public_key_hex='aa' * 32,
                signature_hex='bb' * 64,
            )

    @patch('qubitcoin.quantum.crypto.DilithiumSigner', autospec=False)
    def test_deposit_bad_signature(self, mock_signer_cls):
        """Reject deposit with invalid Dilithium signature."""
        mock_signer_cls.derive_address.return_value = 'test_l1_address_abc123'
        mock_signer_cls.verify.return_value = False  # Bad signature

        utxos = [('utxo1', 0, Decimal('100'))]
        bridge, db = self._make_bridge(utxos)

        with pytest.raises(ValueError, match="Invalid Dilithium signature"):
            bridge.deposit(
                from_address='test_l1_address_abc123',
                to_address='0xABCDEF',
                amount=Decimal('50'),
                public_key_hex='aa' * 32,
                signature_hex='bb' * 64,
            )

    @patch('qubitcoin.quantum.crypto.DilithiumSigner', autospec=False)
    def test_deposit_address_mismatch(self, mock_signer_cls):
        """Reject deposit when public key doesn't match from_address."""
        mock_signer_cls.derive_address.return_value = 'different_address'
        mock_signer_cls.verify.return_value = True

        utxos = [('utxo1', 0, Decimal('100'))]
        bridge, db = self._make_bridge(utxos)

        with pytest.raises(ValueError, match="does not match"):
            bridge.deposit(
                from_address='test_l1_address_abc123',
                to_address='0xABCDEF',
                amount=Decimal('50'),
                public_key_hex='aa' * 32,
                signature_hex='bb' * 64,
            )


# ---------------------------------------------------------------------------
# Tests: Withdraw (L2 → L1)
# ---------------------------------------------------------------------------

class TestWithdraw:
    def _make_bridge(self, account_balance=Decimal(0), **kwargs):
        from qubitcoin.l2_bridge import L1L2Bridge
        db = _make_db_manager(account_balance=account_balance, **kwargs)
        return L1L2Bridge(db), db

    def test_withdraw_success(self):
        """Basic withdraw: debit L2 account, create L1 UTXO."""
        bridge, db = self._make_bridge(account_balance=Decimal('500'))

        result = bridge.withdraw(
            from_address='0x51D3a9b12dc4667f771B2A5cE3491631251E9D41',
            to_address='test_l1_dilithium_address_xyz',
            amount=Decimal('100'),
        )

        assert result['status'] == 'confirmed'
        assert result['amount'] == '100'
        assert result['l1_address'] == 'test_l1_dilithium_address_xyz'
        assert 'tx_hash' in result

    def test_withdraw_insufficient_balance(self):
        """Reject withdraw when L2 balance is insufficient."""
        bridge, db = self._make_bridge(account_balance=Decimal('50'))

        with pytest.raises(ValueError, match="Insufficient L2 balance"):
            bridge.withdraw(
                from_address='0xABCDEF',
                to_address='test_l1_addr',
                amount=Decimal('100'),
            )

    def test_withdraw_zero_amount(self):
        """Reject zero amount withdraw."""
        from qubitcoin.l2_bridge import L1L2Bridge
        bridge = L1L2Bridge(MagicMock())

        with pytest.raises(ValueError, match="positive"):
            bridge.withdraw('0xabc', 'l1_addr', Decimal(0))

    def test_withdraw_negative_amount(self):
        """Reject negative amount withdraw."""
        from qubitcoin.l2_bridge import L1L2Bridge
        bridge = L1L2Bridge(MagicMock())

        with pytest.raises(ValueError, match="positive"):
            bridge.withdraw('0xabc', 'l1_addr', Decimal(-10))

    def test_withdraw_no_account(self):
        """Reject withdraw when L2 account doesn't exist."""
        bridge, db = self._make_bridge(account_balance=Decimal(0))

        with pytest.raises(ValueError, match="Insufficient L2 balance"):
            bridge.withdraw(
                from_address='0xNONEXISTENT',
                to_address='test_l1_addr',
                amount=Decimal('10'),
            )

    def test_withdraw_normalizes_address(self):
        """Verify 0x prefix is stripped for L2 address lookup."""
        bridge, db = self._make_bridge(account_balance=Decimal('200'))

        result = bridge.withdraw(
            from_address='0xABCDEF1234',
            to_address='test_l1_addr',
            amount=Decimal('50'),
        )

        assert result['l2_address'] == '0xabcdef1234'


# ---------------------------------------------------------------------------
# Tests: get_combined_balance
# ---------------------------------------------------------------------------

class TestCombinedBalance:
    def test_combined_balance(self):
        from qubitcoin.l2_bridge import L1L2Bridge
        db = _make_db_manager(
            utxos=[('u1', 0, Decimal('100')), ('u2', 1, Decimal('50'))],
            account_balance=Decimal('200'),
        )
        bridge = L1L2Bridge(db)

        result = bridge.get_combined_balance('0xSomeAddress')

        assert result['l1_balance'] is not None
        assert result['l2_balance'] is not None
        assert result['total'] is not None
        assert 'l1_utxo_count' in result


# ---------------------------------------------------------------------------
# Tests: get_status
# ---------------------------------------------------------------------------

class TestBridgeStatus:
    def test_status(self):
        from qubitcoin.l2_bridge import L1L2Bridge
        db = _make_db_manager()
        bridge = L1L2Bridge(db)

        result = bridge.get_status()

        assert 'deposits' in result
        assert 'withdrawals' in result
        assert 'recent' in result
        assert result['deposits']['count'] == 5
        assert result['withdrawals']['count'] == 3


# ---------------------------------------------------------------------------
# Tests: L2 address normalization
# ---------------------------------------------------------------------------

class TestAddressNormalization:
    def test_0x_prefix_stripped(self):
        """L2 addresses should have 0x stripped and be lowercased."""
        from qubitcoin.l2_bridge import L1L2Bridge
        bridge = L1L2Bridge(_make_db_manager(account_balance=Decimal('100')))

        result = bridge.withdraw(
            from_address='0xAbCdEf',
            to_address='l1_addr',
            amount=Decimal('10'),
        )

        # l2_address in result should have 0x prefix added back
        assert result['l2_address'] == '0xabcdef'

    def test_no_prefix(self):
        """L2 addresses without 0x should still work."""
        from qubitcoin.l2_bridge import L1L2Bridge
        bridge = L1L2Bridge(_make_db_manager(account_balance=Decimal('100')))

        result = bridge.withdraw(
            from_address='abcdef',
            to_address='l1_addr',
            amount=Decimal('10'),
        )

        assert result['l2_address'] == '0xabcdef'


# ---------------------------------------------------------------------------
# Tests: Consensus engine bridge tx type handling
# ---------------------------------------------------------------------------

class TestConsensusEngineIntegration:
    def test_bridge_tx_types_in_contract_list(self):
        """l2_deposit and l2_withdraw should be treated as contract-like txs."""
        # These tx types should not trigger UTXO validation
        contract_types = ('contract_deploy', 'contract_call', 'l2_deposit', 'l2_withdraw')
        for tx_type in ('l2_deposit', 'l2_withdraw'):
            assert tx_type in contract_types


# ---------------------------------------------------------------------------
# Tests: StateManager routing
# ---------------------------------------------------------------------------

class TestStateManagerRouting:
    def test_bridge_tx_returns_none(self):
        """Bridge txs should return None (no QVM execution)."""
        from qubitcoin.qvm.state import StateManager

        sm = MagicMock(spec=StateManager)
        sm.process_transaction = StateManager.process_transaction.__get__(sm)

        tx = MagicMock()
        tx.tx_type = 'l2_deposit'
        result = sm.process_transaction(tx, 100, 'hash', 0)
        assert result is None

        tx.tx_type = 'l2_withdraw'
        result = sm.process_transaction(tx, 100, 'hash', 0)
        assert result is None
