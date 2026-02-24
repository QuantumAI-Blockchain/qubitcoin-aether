"""Unit tests for mining engine — start/stop, coinbase creation, proof generation, stats."""
import pytest
from decimal import Decimal
from unittest.mock import MagicMock, patch, PropertyMock
import time
import hashlib


class TestMiningEngineInit:
    """Test mining engine initialization and lifecycle."""

    def _make_engine(self, **overrides):
        from qubitcoin.mining.engine import MiningEngine
        qe = MagicMock()
        ce = MagicMock()
        db = MagicMock()
        console = MagicMock()
        kwargs = dict(
            quantum_engine=qe,
            consensus_engine=ce,
            db_manager=db,
            console=console,
        )
        kwargs.update(overrides)
        return MiningEngine(**kwargs)

    def test_init_defaults(self):
        """Engine initializes with expected defaults."""
        eng = self._make_engine()
        assert eng.is_mining is False
        assert eng.mining_thread is None
        assert eng.stats['blocks_found'] == 0
        assert eng.stats['total_attempts'] == 0

    def test_start_sets_mining_flag(self):
        """start() sets is_mining and creates thread."""
        eng = self._make_engine()
        with patch.object(eng, '_mine_loop'):
            eng.start()
            assert eng.is_mining is True
            assert eng.mining_thread is not None
            eng.stop()

    def test_start_idempotent(self):
        """Calling start() twice does not create second thread."""
        eng = self._make_engine()
        with patch.object(eng, '_mine_loop'):
            eng.start()
            first_thread = eng.mining_thread
            eng.start()  # second call
            assert eng.mining_thread is first_thread
            eng.stop()

    def test_stop_clears_flag(self):
        """stop() clears is_mining flag."""
        eng = self._make_engine()
        eng.is_mining = True
        eng.mining_thread = MagicMock()
        eng.mining_thread.join = MagicMock()
        eng.stop()
        assert eng.is_mining is False

    def test_stop_noop_when_not_mining(self):
        """stop() is safe to call when not mining."""
        eng = self._make_engine()
        eng.stop()  # should not raise
        assert eng.is_mining is False


class TestCoinbaseCreation:
    """Test coinbase transaction creation."""

    def _make_engine(self):
        from qubitcoin.mining.engine import MiningEngine
        return MiningEngine(
            quantum_engine=MagicMock(),
            consensus_engine=MagicMock(),
            db_manager=MagicMock(),
            console=MagicMock(),
        )

    def test_coinbase_no_pending_txs(self):
        """Coinbase with no pending transactions has reward only."""
        eng = self._make_engine()
        reward = Decimal('15.27')
        cb = eng._create_coinbase(height=1, reward=reward, pending_txs=[])
        assert cb.fee == Decimal(0)
        assert cb.inputs == []
        assert len(cb.outputs) == 1
        assert cb.outputs[0]['amount'] == reward

    def test_coinbase_includes_fees(self):
        """Coinbase amount includes miner's share of fees (after burn)."""
        eng = self._make_engine()
        reward = Decimal('15.27')
        tx1 = MagicMock()
        tx1.fee = Decimal('0.001')
        tx2 = MagicMock()
        tx2.fee = Decimal('0.002')
        cb = eng._create_coinbase(height=5, reward=reward, pending_txs=[tx1, tx2])
        total_fees = Decimal('0.003')
        from qubitcoin.config import Config
        burn_pct = Decimal(str(Config.FEE_BURN_PERCENTAGE))
        burned = (total_fees * burn_pct).quantize(Decimal('0.00000001'))
        expected_total = reward + total_fees - burned
        assert cb.outputs[0]['amount'] == expected_total

    def test_coinbase_txid_is_sha256_hex(self):
        """Coinbase txid is valid SHA-256 hex string."""
        eng = self._make_engine()
        cb = eng._create_coinbase(height=1, reward=Decimal('15.27'), pending_txs=[])
        assert len(cb.txid) == 64  # sha256 hex
        int(cb.txid, 16)  # must parse as hex

    def test_coinbase_unique_per_height(self):
        """Different heights produce different coinbase txids."""
        eng = self._make_engine()
        cb1 = eng._create_coinbase(height=1, reward=Decimal('15.27'), pending_txs=[])
        cb2 = eng._create_coinbase(height=2, reward=Decimal('15.27'), pending_txs=[])
        assert cb1.txid != cb2.txid


class TestProofCreation:
    """Test quantum proof data creation."""

    def _make_engine(self):
        from qubitcoin.mining.engine import MiningEngine
        return MiningEngine(
            quantum_engine=MagicMock(),
            consensus_engine=MagicMock(),
            db_manager=MagicMock(),
            console=MagicMock(),
        )

    @patch('qubitcoin.mining.engine.Config')
    @patch('qubitcoin.mining.engine.Dilithium2')
    def test_proof_structure(self, mock_dilithium, mock_config):
        """Proof data contains all required fields."""
        import numpy as np
        mock_config.PRIVATE_KEY_HEX = 'aa' * 32
        mock_config.PUBLIC_KEY_HEX = 'bb' * 32
        mock_config.ADDRESS = 'qbc1test'
        mock_dilithium.sign.return_value = b'\x00' * 64

        eng = self._make_engine()
        proof = eng._create_proof(
            hamiltonian={'test': True},
            params=np.array([0.1, 0.2, 0.3]),
            energy=-1.5,
            prev_hash='0' * 64,
            height=10,
        )
        assert 'challenge' in proof
        assert 'params' in proof
        assert 'energy' in proof
        assert 'prev_hash' in proof
        assert 'height' in proof
        assert 'signature' in proof
        assert 'public_key' in proof
        assert 'miner_address' in proof
        assert proof['energy'] == -1.5
        assert proof['height'] == 10

    @patch('qubitcoin.mining.engine.Config')
    @patch('qubitcoin.mining.engine.Dilithium2')
    def test_proof_params_are_list(self, mock_dilithium, mock_config):
        """VQE params are serialized as list (not numpy array)."""
        import numpy as np
        mock_config.PRIVATE_KEY_HEX = 'aa' * 32
        mock_config.PUBLIC_KEY_HEX = 'bb' * 32
        mock_config.ADDRESS = 'qbc1test'
        mock_dilithium.sign.return_value = b'\x00' * 64

        eng = self._make_engine()
        proof = eng._create_proof(
            hamiltonian={},
            params=np.array([0.5, 1.0]),
            energy=-1.0,
            prev_hash='0' * 64,
            height=1,
        )
        assert isinstance(proof['params'], list)


class TestPrevHash:
    """Test previous block hash retrieval."""

    def _make_engine(self):
        from qubitcoin.mining.engine import MiningEngine
        return MiningEngine(
            quantum_engine=MagicMock(),
            consensus_engine=MagicMock(),
            db_manager=MagicMock(),
            console=MagicMock(),
        )

    def test_genesis_prev_hash(self):
        """Height -1 or below returns zero hash."""
        eng = self._make_engine()
        assert eng._get_prev_hash(-1) == '0' * 64

    def test_known_prev_hash(self):
        """Returns block_hash from previous block."""
        eng = self._make_engine()
        mock_block = MagicMock()
        mock_block.block_hash = 'ab' * 32
        eng.db.get_block.return_value = mock_block
        assert eng._get_prev_hash(5) == 'ab' * 32

    def test_missing_block_falls_back(self):
        """Returns zero hash if previous block is missing."""
        eng = self._make_engine()
        eng.db.get_block.return_value = None
        result = eng._get_prev_hash(5)
        assert result == '0' * 64
