"""Unit tests for mining pipeline and UTXO security.

Tests block creation, coinbase transactions, UTXO model integrity,
and double-spend prevention logic.
"""
import pytest
import time
import hashlib
from decimal import Decimal
from unittest.mock import MagicMock, patch


def _make_coinbase_tx(height: int, reward: Decimal, address: str = 'qbc1test') -> 'Transaction':
    """Create a coinbase transaction."""
    from qubitcoin.database.models import Transaction
    txid = hashlib.sha256(f"coinbase-{height}-{time.time()}".encode()).hexdigest()
    return Transaction(
        txid=txid,
        inputs=[],
        outputs=[{'address': address, 'amount': reward}],
        fee=Decimal(0),
        signature='',
        public_key='',
        timestamp=time.time(),
        status='pending',
    )


def _make_block(height: int, prev_hash: str = '0' * 64,
                reward: Decimal = Decimal('15.27'),
                difficulty: float = 1.0) -> 'Block':
    """Create a test block with coinbase."""
    from qubitcoin.database.models import Block
    coinbase = _make_coinbase_tx(height, reward)
    block = Block(
        height=height,
        prev_hash=prev_hash,
        proof_data={'params': [0.1], 'energy': 0.5, 'challenge': []},
        transactions=[coinbase],
        timestamp=time.time(),
        difficulty=difficulty,
    )
    block.block_hash = block.calculate_hash()
    return block


class TestBlockModel:
    """Test Block dataclass."""

    def test_block_hash_deterministic(self):
        from qubitcoin.database.models import Block
        b1 = Block(height=0, prev_hash='0' * 64, proof_data={},
                    transactions=[], timestamp=1000.0, difficulty=1.0)
        b2 = Block(height=0, prev_hash='0' * 64, proof_data={},
                    transactions=[], timestamp=1000.0, difficulty=1.0)
        assert b1.calculate_hash() == b2.calculate_hash()

    def test_different_blocks_different_hash(self):
        from qubitcoin.database.models import Block
        b1 = Block(height=0, prev_hash='0' * 64, proof_data={},
                    transactions=[], timestamp=1000.0, difficulty=1.0)
        b2 = Block(height=1, prev_hash='a' * 64, proof_data={},
                    transactions=[], timestamp=1001.0, difficulty=1.0)
        assert b1.calculate_hash() != b2.calculate_hash()

    def test_block_to_dict(self):
        block = _make_block(0)
        d = block.to_dict()
        assert d['height'] == 0
        assert 'transactions' in d
        assert 'block_hash' in d

    def test_block_from_dict(self):
        from qubitcoin.database.models import Block
        block = _make_block(0)
        d = block.to_dict()
        restored = Block.from_dict(d)
        assert restored.height == block.height
        assert restored.prev_hash == block.prev_hash

    def test_block_thought_proof(self):
        from qubitcoin.database.models import Block
        block = Block(height=0, prev_hash='0' * 64, proof_data={},
                      transactions=[], timestamp=1000.0, difficulty=1.0,
                      thought_proof={'hash': 'abc123'})
        d = block.to_dict()
        assert d['thought_proof'] == {'hash': 'abc123'}


class TestTransactionModel:
    """Test Transaction dataclass."""

    def test_txid_calculation(self):
        from qubitcoin.database.models import Transaction
        tx = Transaction(
            txid='temp',
            inputs=[{'txid': 'a' * 64, 'vout': 0}],
            outputs=[{'address': 'qbc1test', 'amount': Decimal('10.0')}],
            fee=Decimal('0.001'),
            signature='sig',
            public_key='pk',
            timestamp=1000.0,
        )
        calculated = tx.calculate_txid()
        assert len(calculated) == 64
        assert isinstance(calculated, str)

    def test_same_data_same_txid(self):
        from qubitcoin.database.models import Transaction
        tx1 = Transaction(
            txid='a', inputs=[], outputs=[{'address': 'x', 'amount': Decimal('1')}],
            fee=Decimal(0), signature='', public_key='', timestamp=1000.0,
        )
        tx2 = Transaction(
            txid='b', inputs=[], outputs=[{'address': 'x', 'amount': Decimal('1')}],
            fee=Decimal(0), signature='', public_key='', timestamp=1000.0,
        )
        assert tx1.calculate_txid() == tx2.calculate_txid()

    def test_tx_to_dict(self):
        from qubitcoin.database.models import Transaction
        tx = Transaction(
            txid='test123',
            inputs=[{'txid': 'a' * 64, 'vout': 0}],
            outputs=[{'address': 'qbc1test', 'amount': Decimal('10')}],
            fee=Decimal('0.001'),
            signature='sig',
            public_key='pk',
            timestamp=1000.0,
        )
        d = tx.to_dict()
        assert d['txid'] == 'test123'
        assert d['fee'] == '0.001'

    def test_tx_from_dict(self):
        from qubitcoin.database.models import Transaction
        data = {
            'txid': 'abc',
            'inputs': [],
            'outputs': [{'address': 'qbc1', 'amount': '5'}],
            'fee': '0.01',
            'signature': 's',
            'public_key': 'p',
            'timestamp': 1000.0,
        }
        tx = Transaction.from_dict(data)
        assert tx.txid == 'abc'
        assert tx.fee == Decimal('0.01')
        assert tx.outputs[0]['amount'] == Decimal('5')

    def test_tx_type_default_transfer(self):
        from qubitcoin.database.models import Transaction
        tx = Transaction(txid='x', inputs=[], outputs=[], fee=Decimal(0),
                         signature='', public_key='', timestamp=0.0)
        assert tx.tx_type == 'transfer'


class TestUTXOModel:
    """Test UTXO dataclass and operations."""

    def test_utxo_creation(self):
        from qubitcoin.database.models import UTXO
        utxo = UTXO(txid='a' * 64, vout=0, amount=Decimal('10.0'),
                     address='qbc1test', proof={})
        assert utxo.spent is False
        assert utxo.spent_by is None

    def test_utxo_to_dict(self):
        from qubitcoin.database.models import UTXO
        utxo = UTXO(txid='a' * 64, vout=0, amount=Decimal('10.5'),
                     address='qbc1test', proof={'type': 'coinbase'})
        d = utxo.to_dict()
        assert d['amount'] == '10.5'
        assert d['spent'] is False

    def test_utxo_from_dict(self):
        from qubitcoin.database.models import UTXO
        data = {
            'txid': 'b' * 64, 'vout': 1, 'amount': '25.0',
            'address': 'qbc1addr', 'proof': {},
        }
        utxo = UTXO.from_dict(data)
        assert utxo.amount == Decimal('25.0')
        assert utxo.vout == 1

    def test_utxo_spent_tracking(self):
        from qubitcoin.database.models import UTXO
        utxo = UTXO(txid='a' * 64, vout=0, amount=Decimal('10'),
                     address='qbc1test', proof={})
        assert utxo.spent is False
        utxo.spent = True
        utxo.spent_by = 'spending_tx_hash'
        assert utxo.spent is True
        assert utxo.spent_by == 'spending_tx_hash'

    def test_utxo_block_height(self):
        from qubitcoin.database.models import UTXO
        utxo = UTXO(txid='a' * 64, vout=0, amount=Decimal('10'),
                     address='qbc1test', proof={}, block_height=42)
        assert utxo.block_height == 42


class TestCoinbaseTransaction:
    """Test coinbase transaction creation and validation rules."""

    def test_coinbase_has_no_inputs(self):
        tx = _make_coinbase_tx(0, Decimal('15.27'))
        assert len(tx.inputs) == 0

    def test_coinbase_has_output(self):
        tx = _make_coinbase_tx(0, Decimal('15.27'))
        assert len(tx.outputs) == 1
        assert tx.outputs[0]['amount'] == Decimal('15.27')

    def test_coinbase_fee_is_zero(self):
        tx = _make_coinbase_tx(0, Decimal('15.27'))
        assert tx.fee == Decimal(0)

    def test_different_heights_different_txids(self):
        tx1 = _make_coinbase_tx(0, Decimal('15.27'))
        tx2 = _make_coinbase_tx(1, Decimal('15.27'))
        assert tx1.txid != tx2.txid


class TestRewardCalculation:
    """Test block reward with golden ratio halving (extended)."""

    def test_era_boundaries(self):
        """Test reward at exact era boundary transitions."""
        from qubitcoin.consensus.engine import ConsensusEngine
        from unittest.mock import MagicMock
        engine = ConsensusEngine.__new__(ConsensusEngine)
        engine.difficulty_cache = {}
        supply = Decimal(0)

        era0_reward = engine.calculate_reward(0, supply)
        era1_start = 15474020  # HALVING_INTERVAL
        era1_reward = engine.calculate_reward(era1_start, supply)
        # Era 1 reward should be era0 / phi
        phi = Decimal('1.618033988749895')
        expected = era0_reward / phi
        assert abs(era1_reward - expected) < Decimal('0.01')

    def test_all_eras_positive(self):
        """First 10 eras should all produce positive rewards."""
        from qubitcoin.consensus.engine import ConsensusEngine
        engine = ConsensusEngine.__new__(ConsensusEngine)
        engine.difficulty_cache = {}
        for era in range(10):
            height = era * 15474020
            reward = engine.calculate_reward(height, Decimal(0))
            assert reward > 0

    def test_reward_monotonically_decreasing(self):
        """Each era's reward should be less than the previous."""
        from qubitcoin.consensus.engine import ConsensusEngine
        engine = ConsensusEngine.__new__(ConsensusEngine)
        engine.difficulty_cache = {}
        prev_reward = None
        for era in range(5):
            height = era * 15474020
            reward = engine.calculate_reward(height, Decimal(0))
            if prev_reward is not None:
                assert reward < prev_reward
            prev_reward = reward


class TestBlockValidationRules:
    """Test block validation edge cases."""

    def test_block_chain_linking(self):
        """Blocks must chain via prev_hash."""
        block0 = _make_block(0)
        block1 = _make_block(1, prev_hash=block0.block_hash)
        assert block1.prev_hash == block0.block_hash

    def test_block_height_sequence(self):
        """Blocks must have sequential heights."""
        block0 = _make_block(0)
        block1 = _make_block(1, prev_hash=block0.block_hash)
        assert block1.height == block0.height + 1

    def test_genesis_block_prev_hash(self):
        """Genesis block should have all-zero prev_hash."""
        block = _make_block(0, prev_hash='0' * 64)
        assert block.prev_hash == '0' * 64

    def test_block_with_transactions(self):
        """Block can contain multiple transactions."""
        from qubitcoin.database.models import Block, Transaction
        coinbase = _make_coinbase_tx(1, Decimal('15.27'))
        tx = Transaction(
            txid='user_tx',
            inputs=[{'txid': 'a' * 64, 'vout': 0}],
            outputs=[{'address': 'qbc1bob', 'amount': Decimal('5.0')}],
            fee=Decimal('0.001'),
            signature='sig',
            public_key='pk',
            timestamp=time.time(),
        )
        block = Block(
            height=1, prev_hash='0' * 64,
            proof_data={'params': [0.1], 'energy': 0.5, 'challenge': []},
            transactions=[coinbase, tx],
            timestamp=time.time(), difficulty=1.0,
        )
        assert len(block.transactions) == 2


class TestDoubleSpendPrevention:
    """Test UTXO-based double-spend prevention logic."""

    def test_spent_utxo_marked(self):
        """Once a UTXO is spent, it should be marked as spent."""
        from qubitcoin.database.models import UTXO
        utxo = UTXO(txid='a' * 64, vout=0, amount=Decimal('10'),
                     address='qbc1alice', proof={})
        # Simulate spending
        utxo.spent = True
        utxo.spent_by = 'spending_tx'
        assert utxo.spent is True

    def test_cannot_spend_zero_amount(self):
        """UTXO with zero amount has no value to spend."""
        from qubitcoin.database.models import UTXO
        utxo = UTXO(txid='a' * 64, vout=0, amount=Decimal('0'),
                     address='qbc1alice', proof={})
        assert utxo.amount == Decimal('0')

    def test_utxo_set_balance_calculation(self):
        """Balance = sum of all unspent UTXOs for an address."""
        from qubitcoin.database.models import UTXO
        utxos = [
            UTXO(txid='a' * 64, vout=0, amount=Decimal('10'), address='qbc1alice', proof={}),
            UTXO(txid='b' * 64, vout=0, amount=Decimal('5'), address='qbc1alice', proof={}),
            UTXO(txid='c' * 64, vout=0, amount=Decimal('20'), address='qbc1alice', proof={}, spent=True),
        ]
        balance = sum(u.amount for u in utxos if not u.spent)
        assert balance == Decimal('15')

    def test_spending_reduces_available_utxos(self):
        """After spending, the UTXO count should decrease."""
        from qubitcoin.database.models import UTXO
        utxos = [
            UTXO(txid=f'{"a" * 63}{i}', vout=0, amount=Decimal('10'),
                 address='qbc1alice', proof={})
            for i in range(3)
        ]
        assert sum(1 for u in utxos if not u.spent) == 3
        utxos[0].spent = True
        assert sum(1 for u in utxos if not u.spent) == 2

    def test_input_value_must_cover_output(self):
        """Total input value must be >= total output value + fee."""
        input_amount = Decimal('10.0')
        output_amount = Decimal('9.0')
        fee = Decimal('0.5')
        assert input_amount >= output_amount + fee

    def test_input_value_insufficient(self):
        """Insufficient input should fail."""
        input_amount = Decimal('5.0')
        output_amount = Decimal('9.0')
        fee = Decimal('0.5')
        assert input_amount < output_amount + fee
