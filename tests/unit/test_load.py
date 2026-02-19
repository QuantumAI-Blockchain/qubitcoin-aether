"""Load tests — concurrent mining simulation and high transaction volume."""
import pytest
import time
import threading
from decimal import Decimal
from unittest.mock import MagicMock, patch


class TestConcurrentMining:
    """Simulate concurrent mining operations under load."""

    def _make_engine(self):
        from qubitcoin.mining.engine import MiningEngine
        return MiningEngine(
            quantum_engine=MagicMock(),
            consensus_engine=MagicMock(),
            db_manager=MagicMock(),
            console=MagicMock(),
        )

    def test_rapid_coinbase_creation(self):
        """Create 100 coinbase transactions rapidly without collision."""
        eng = self._make_engine()
        reward = Decimal('15.27')
        txids = set()
        for height in range(100):
            cb = eng._create_coinbase(height=height, reward=reward, pending_txs=[])
            assert cb.txid not in txids, f"Coinbase txid collision at height {height}"
            txids.add(cb.txid)
        assert len(txids) == 100

    def test_start_stop_rapid_cycling(self):
        """Rapidly start/stop mining without deadlocks or crashes."""
        eng = self._make_engine()
        with patch.object(eng, '_mine_loop'):
            for _ in range(10):
                eng.start()
                assert eng.is_mining is True
                eng.stop()
                assert eng.is_mining is False

    def test_concurrent_stat_reads(self):
        """Multiple threads reading mining stats simultaneously."""
        eng = self._make_engine()
        eng.stats['blocks_found'] = 5
        eng.stats['total_attempts'] = 100
        errors = []

        def read_stats():
            try:
                for _ in range(50):
                    _ = eng.stats['blocks_found']
                    _ = eng.stats['total_attempts']
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=read_stats) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)
        assert len(errors) == 0, f"Concurrent read errors: {errors}"

    def test_coinbase_with_many_pending_txs(self):
        """Coinbase creation with 1000 pending transactions."""
        eng = self._make_engine()
        reward = Decimal('15.27')
        pending = []
        for i in range(1000):
            tx = MagicMock()
            tx.fee = Decimal('0.001')
            pending.append(tx)
        cb = eng._create_coinbase(height=1, reward=reward, pending_txs=pending)
        expected = reward + Decimal('1.0')  # 1000 * 0.001
        assert cb.outputs[0]['amount'] == expected


class TestHighVolumeTransactions:
    """Test transaction processing at high volume."""

    def test_rapid_utxo_creation(self):
        """Create 1000 UTXO objects rapidly."""
        from qubitcoin.database.models import UTXO
        utxos = []
        for i in range(1000):
            utxo = UTXO(
                txid=f'{i:064x}',
                vout=0,
                amount=Decimal('1.0'),
                address=f'qbc1test{i}',
                proof={},
            )
            utxos.append(utxo)
        assert len(utxos) == 1000
        assert utxos[999].txid == f'{999:064x}'

    def test_rapid_transaction_creation(self):
        """Create 500 transaction objects rapidly."""
        from qubitcoin.database.models import Transaction
        txs = []
        for i in range(500):
            tx = Transaction(
                txid=f'{i:064x}',
                inputs=[{'txid': f'{i-1:064x}', 'vout': 0}] if i > 0 else [],
                outputs=[{'address': f'qbc1addr{i}', 'amount': str(Decimal('1.0'))}],
                timestamp=time.time(),
                signature='aa' * 64,
                public_key='bb' * 32,
                fee=Decimal('0.001'),
            )
            txs.append(tx)
        assert len(txs) == 500

    def test_block_with_max_transactions(self):
        """Create a block containing 333 transactions (theoretical max per MB)."""
        from qubitcoin.database.models import Block, Transaction
        txs = []
        for i in range(333):
            tx = Transaction(
                txid=f'{i:064x}',
                inputs=[],
                outputs=[{'address': 'qbc1test', 'amount': '1.0'}],
                timestamp=time.time(),
                signature='aa' * 64,
                public_key='bb' * 32,
                fee=Decimal('0.001'),
            )
            txs.append(tx)
        block = Block(
            height=1,
            prev_hash='0' * 64,
            proof_data={'energy': -1.0},
            transactions=txs,
            timestamp=time.time(),
            difficulty=1.0,
        )
        assert len(block.transactions) == 333
        block_hash = block.calculate_hash()
        assert len(block_hash) == 64


class TestConsensusLoad:
    """Test consensus engine under load conditions."""

    def _make_engine(self):
        from qubitcoin.consensus.engine import ConsensusEngine
        return ConsensusEngine(
            db_manager=MagicMock(),
            quantum_engine=MagicMock(),
            p2p_network=MagicMock(),
        )

    def test_rapid_difficulty_queries(self):
        """Query difficulty 100 times rapidly."""
        eng = self._make_engine()
        db = MagicMock()
        db.get_block.return_value = MagicMock(difficulty=1.0, timestamp=time.time())
        for height in range(100):
            d = eng.calculate_difficulty(height, db)
            assert isinstance(d, (int, float, Decimal))

    def test_rapid_reward_calculations(self):
        """Calculate block rewards for heights 0 through 999."""
        eng = self._make_engine()
        total_supply = Decimal('0')
        rewards = []
        for h in range(1000):
            r = eng.calculate_reward(h, total_supply)
            assert r > 0
            rewards.append(r)
            total_supply += r
        # Rewards should be non-increasing (phi-halving)
        assert rewards[0] >= rewards[-1]
