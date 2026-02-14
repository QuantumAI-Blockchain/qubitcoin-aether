"""Unit tests for UTXO fee collector and fee integration.

Tests:
  - FeeCollector UTXO selection, fee deduction, change creation
  - FeeCollector audit log
  - AetherChat fee deduction integration
  - ContractEngine fee deduction integration
  - Edge cases: insufficient balance, no treasury, zero fee
"""
import pytest
from decimal import Decimal
from unittest.mock import MagicMock, patch, PropertyMock
from contextlib import contextmanager

from qubitcoin.database.models import UTXO
from qubitcoin.utils.fee_collector import FeeCollector, FeeRecord


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_utxo(txid: str, vout: int, amount: Decimal, address: str,
               block_height: int = 100) -> UTXO:
    """Create a test UTXO."""
    return UTXO(
        txid=txid, vout=vout, amount=amount,
        address=address, proof={}, block_height=block_height,
    )


class FakeSession:
    """Minimal session mock that supports execute/commit."""
    def __init__(self):
        self.committed = False
        self.executed = []

    def execute(self, stmt, params=None):
        self.executed.append((str(stmt), params))
        return MagicMock()

    def commit(self):
        self.committed = True


class FakeDBManager:
    """In-memory DB manager for testing fee collector."""
    def __init__(self):
        self.utxos: dict = {}  # address -> [UTXO]
        self.spent: list = []
        self.created_utxos: list = []
        self._session = FakeSession()
        self._height = 100

    def get_balance(self, address: str) -> Decimal:
        return sum(u.amount for u in self.utxos.get(address, []) if not u.spent)

    def get_utxos(self, address: str):
        return [u for u in self.utxos.get(address, []) if not u.spent]

    def get_current_height(self) -> int:
        return self._height

    @contextmanager
    def get_session(self):
        yield self._session

    def mark_utxos_spent(self, inputs, txid, session):
        for inp in inputs:
            for addr, utxo_list in self.utxos.items():
                for u in utxo_list:
                    if u.txid == inp['txid'] and u.vout == inp['vout']:
                        u.spent = True
                        u.spent_by = txid
                        self.spent.append(u)

    def create_utxos(self, txid, outputs, block_height, proof, session=None):
        for vout, output in enumerate(outputs):
            new_utxo = _make_utxo(txid, vout, Decimal(str(output['amount'])),
                                   output['address'], block_height)
            addr = output['address']
            self.utxos.setdefault(addr, []).append(new_utxo)
            self.created_utxos.append(new_utxo)

    def add_utxo(self, utxo: UTXO):
        self.utxos.setdefault(utxo.address, []).append(utxo)


# ---------------------------------------------------------------------------
# FeeCollector: core tests
# ---------------------------------------------------------------------------

class TestFeeCollectorCore:
    """Test FeeCollector UTXO selection and fee deduction."""

    def _setup(self):
        db = FakeDBManager()
        db.add_utxo(_make_utxo('aaa', 0, Decimal('10.0'), 'user1'))
        db.add_utxo(_make_utxo('bbb', 0, Decimal('5.0'), 'user1'))
        db.add_utxo(_make_utxo('ccc', 0, Decimal('2.0'), 'user1'))
        return db, FeeCollector(db)

    def test_collect_fee_success(self):
        """Fee deduction succeeds with sufficient balance."""
        db, fc = self._setup()
        with patch.object(type(fc), '_compute_fee_txid', return_value='fee_tx_001'):
            pass
        success, msg, record = fc.collect_fee(
            'user1', Decimal('3.0'), 'aether_chat', 'treasury1'
        )
        assert success, msg
        assert record is not None
        assert record.fee_amount == Decimal('3.0')
        assert record.treasury_address == 'treasury1'
        assert record.fee_type == 'aether_chat'
        # Balance should decrease
        assert db.get_balance('user1') < Decimal('17.0')

    def test_collect_fee_creates_change(self):
        """Change output is created when input exceeds fee."""
        db, fc = self._setup()
        success, msg, record = fc.collect_fee(
            'user1', Decimal('3.0'), 'aether_chat', 'treasury1'
        )
        assert success
        assert record.change_amount > 0
        # Treasury should have the fee
        treasury_balance = db.get_balance('treasury1')
        assert treasury_balance == Decimal('3.0')

    def test_collect_fee_exact_amount(self):
        """No change when input exactly matches fee."""
        db = FakeDBManager()
        db.add_utxo(_make_utxo('exact', 0, Decimal('5.0'), 'user2'))
        fc = FeeCollector(db)
        success, msg, record = fc.collect_fee(
            'user2', Decimal('5.0'), 'contract_deploy', 'treasury1'
        )
        assert success
        assert record.change_amount == Decimal('0')

    def test_collect_fee_insufficient_balance(self):
        """Fee deduction fails with insufficient balance."""
        db = FakeDBManager()
        db.add_utxo(_make_utxo('small', 0, Decimal('1.0'), 'user3'))
        fc = FeeCollector(db)
        success, msg, record = fc.collect_fee(
            'user3', Decimal('5.0'), 'aether_chat', 'treasury1'
        )
        assert not success
        assert 'Insufficient' in msg
        assert record is None

    def test_collect_fee_no_utxos(self):
        """Fee deduction fails when address has no UTXOs."""
        db = FakeDBManager()
        fc = FeeCollector(db)
        success, msg, record = fc.collect_fee(
            'empty_user', Decimal('1.0'), 'aether_chat', 'treasury1'
        )
        assert not success
        assert record is None

    def test_collect_fee_zero_amount(self):
        """Zero fee is a no-op success."""
        db, fc = self._setup()
        success, msg, record = fc.collect_fee(
            'user1', Decimal('0'), 'aether_chat', 'treasury1'
        )
        assert success
        assert record is None
        assert 'No fee' in msg

    def test_collect_fee_no_treasury(self):
        """No treasury address configured: fee is skipped."""
        db, fc = self._setup()
        with patch('qubitcoin.utils.fee_collector.Config') as mock_cfg:
            mock_cfg.AETHER_FEE_TREASURY_ADDRESS = ''
            mock_cfg.CONTRACT_FEE_TREASURY_ADDRESS = ''
            success, msg, record = fc.collect_fee(
                'user1', Decimal('1.0'), 'aether_chat', ''
            )
        assert success
        assert record is None
        assert 'skipped' in msg.lower()

    def test_collect_fee_payer_is_treasury(self):
        """Payer is treasury: fee is skipped."""
        db, fc = self._setup()
        success, msg, record = fc.collect_fee(
            'treasury1', Decimal('1.0'), 'aether_chat', 'treasury1'
        )
        assert success
        assert record is None

    def test_utxo_selection_largest_first(self):
        """UTXOs are selected largest-first to minimize inputs."""
        db = FakeDBManager()
        db.add_utxo(_make_utxo('s1', 0, Decimal('1.0'), 'user4'))
        db.add_utxo(_make_utxo('s2', 0, Decimal('3.0'), 'user4'))
        db.add_utxo(_make_utxo('s3', 0, Decimal('7.0'), 'user4'))
        fc = FeeCollector(db)

        selected, total = fc._select_utxos(db.get_utxos('user4'), Decimal('4.0'))
        # Should pick the 7.0 UTXO (largest first covers 4.0)
        assert len(selected) == 1
        assert selected[0].amount == Decimal('7.0')

    def test_utxo_selection_multiple(self):
        """Multiple UTXOs selected when no single one is sufficient."""
        db = FakeDBManager()
        db.add_utxo(_make_utxo('m1', 0, Decimal('2.0'), 'user5'))
        db.add_utxo(_make_utxo('m2', 0, Decimal('2.0'), 'user5'))
        db.add_utxo(_make_utxo('m3', 0, Decimal('2.0'), 'user5'))
        fc = FeeCollector(db)

        selected, total = fc._select_utxos(db.get_utxos('user5'), Decimal('5.0'))
        assert len(selected) == 3
        assert total == Decimal('6.0')


# ---------------------------------------------------------------------------
# FeeCollector: audit log
# ---------------------------------------------------------------------------

class TestFeeCollectorAudit:
    """Test fee audit logging."""

    def test_audit_log_records(self):
        """Fee collections are logged in audit trail."""
        db = FakeDBManager()
        db.add_utxo(_make_utxo('a1', 0, Decimal('100.0'), 'user1'))
        fc = FeeCollector(db)

        fc.collect_fee('user1', Decimal('1.0'), 'aether_chat', 'treasury1')
        fc.collect_fee('user1', Decimal('2.0'), 'contract_deploy', 'treasury2')

        log = fc.get_audit_log()
        assert len(log) == 2
        assert log[0]['fee_type'] == 'contract_deploy'  # most recent first
        assert log[1]['fee_type'] == 'aether_chat'

    def test_audit_log_filter(self):
        """Audit log can be filtered by fee type."""
        db = FakeDBManager()
        db.add_utxo(_make_utxo('a1', 0, Decimal('100.0'), 'user1'))
        fc = FeeCollector(db)

        fc.collect_fee('user1', Decimal('1.0'), 'aether_chat', 'treasury1')
        fc.collect_fee('user1', Decimal('2.0'), 'contract_deploy', 'treasury1')

        log = fc.get_audit_log(fee_type='aether_chat')
        assert len(log) == 1
        assert log[0]['fee_type'] == 'aether_chat'

    def test_total_fees_collected(self):
        """Total fees calculated correctly."""
        db = FakeDBManager()
        db.add_utxo(_make_utxo('a1', 0, Decimal('100.0'), 'user1'))
        fc = FeeCollector(db)

        fc.collect_fee('user1', Decimal('1.5'), 'aether_chat', 'treasury1')
        fc.collect_fee('user1', Decimal('2.5'), 'aether_query', 'treasury1')
        fc.collect_fee('user1', Decimal('5.0'), 'contract_deploy', 'treasury1')

        assert fc.get_total_fees_collected() == Decimal('9.0')
        assert fc.get_total_fees_collected('aether_chat') == Decimal('1.5')

    def test_audit_log_capacity(self):
        """Audit log evicts oldest entries when over capacity."""
        db = FakeDBManager()
        db.add_utxo(_make_utxo('a1', 0, Decimal('100000.0'), 'user1'))
        fc = FeeCollector(db)
        fc._max_audit_entries = 5

        for i in range(10):
            fc.collect_fee('user1', Decimal('0.1'), 'aether_chat', 'treasury1')

        assert len(fc._audit_log) == 5


# ---------------------------------------------------------------------------
# AetherChat fee integration
# ---------------------------------------------------------------------------

class TestAetherChatFeeIntegration:
    """Test that AetherChat deducts fees via FeeCollector."""

    def _make_chat(self, fee_collector=None):
        from qubitcoin.aether.chat import AetherChat
        engine = MagicMock()
        engine.kg = None
        engine.reasoning = None
        engine.phi = None
        db = MagicMock()
        chat = AetherChat(engine, db, fee_collector=fee_collector)
        return chat

    def test_chat_no_fee_collector(self):
        """Chat works without fee collector (backward compatible)."""
        chat = self._make_chat()
        session = chat.create_session('user1')
        result = chat.process_message(session.session_id, "hello")
        assert 'error' not in result
        assert 'response' in result

    def test_chat_free_tier_no_deduction(self):
        """Free tier messages don't trigger fee deduction."""
        fc_mock = MagicMock()
        chat = self._make_chat(fee_collector=fc_mock)
        session = chat.create_session('user1')
        # First message should be free (within free tier)
        result = chat.process_message(session.session_id, "hello")
        assert 'error' not in result
        fc_mock.collect_fee.assert_not_called()

    def test_chat_fee_deduction_after_free_tier(self):
        """Fee is deducted after free tier messages are exhausted."""
        db = FakeDBManager()
        db.add_utxo(_make_utxo('u1', 0, Decimal('100.0'), 'user1'))
        fc = FeeCollector(db)

        from qubitcoin.aether.chat import AetherChat
        engine = MagicMock()
        engine.kg = None
        engine.reasoning = None
        engine.phi = None
        chat = AetherChat(engine, MagicMock(), fee_collector=fc)
        session = chat.create_session('user1')

        # Exhaust free tier (default 5)
        from qubitcoin.config import Config
        for i in range(Config.AETHER_FREE_TIER_MESSAGES):
            chat.process_message(session.session_id, f"free msg {i}")

        # Next message should incur a fee
        with patch.object(Config, 'AETHER_FEE_TREASURY_ADDRESS', 'treasury1'):
            result = chat.process_message(session.session_id, "paid msg")

        assert 'error' not in result
        assert 'fee_paid' in result or db.get_balance('treasury1') > 0

    def test_chat_fee_failure_blocks_message(self):
        """If fee collection fails, message is not processed."""
        fc_mock = MagicMock()
        fc_mock.collect_fee.return_value = (False, "Insufficient balance", None)

        from qubitcoin.aether.chat import AetherChat
        engine = MagicMock()
        engine.kg = None
        engine.reasoning = None
        engine.phi = None
        chat = AetherChat(engine, MagicMock(), fee_collector=fc_mock)
        session = chat.create_session('user1')

        # Exhaust free tier
        from qubitcoin.config import Config
        for i in range(Config.AETHER_FREE_TIER_MESSAGES):
            chat.process_message(session.session_id, f"free {i}")

        result = chat.process_message(session.session_id, "should fail")
        assert 'error' in result
        assert 'Fee payment failed' in result['error']


# ---------------------------------------------------------------------------
# ContractEngine fee integration
# ---------------------------------------------------------------------------

class TestContractEngineFeeIntegration:
    """Test that ContractEngine deducts fees via FeeCollector."""

    def test_engine_accepts_fee_collector(self):
        """ContractEngine initializes with fee_collector param."""
        from qubitcoin.contracts.engine import ContractEngine
        fc = MagicMock()
        calc = MagicMock()
        engine = ContractEngine(MagicMock(), MagicMock(), fee_collector=fc,
                                fee_calculator=calc)
        assert engine.fee_collector is fc
        assert engine.fee_calculator is calc

    def test_engine_backward_compatible(self):
        """ContractEngine works without fee_collector (old behavior)."""
        from qubitcoin.contracts.engine import ContractEngine
        engine = ContractEngine(MagicMock(), MagicMock())
        assert engine.fee_collector is None
        assert engine.fee_calculator is None


# ---------------------------------------------------------------------------
# FeeRecord tests
# ---------------------------------------------------------------------------

class TestFeeRecord:
    """Test FeeRecord serialization."""

    def test_to_dict(self):
        record = FeeRecord(
            fee_txid='abc123',
            payer_address='user1',
            treasury_address='treasury1',
            fee_amount=Decimal('1.5'),
            fee_type='aether_chat',
            timestamp=1000.0,
            block_height=50,
            inputs_consumed=2,
            change_amount=Decimal('3.5'),
        )
        d = record.to_dict()
        assert d['fee_amount'] == '1.5'
        assert d['change_amount'] == '3.5'
        assert d['fee_txid'] == 'abc123'
        assert d['fee_type'] == 'aether_chat'
        assert d['inputs_consumed'] == 2
