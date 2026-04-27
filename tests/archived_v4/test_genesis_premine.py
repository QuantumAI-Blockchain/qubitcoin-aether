"""Dedicated tests for the 33M QBC genesis premine.

Covers config constants, coinbase construction, consensus validation,
and circulation tracking with the premine included.
"""
import pytest
from decimal import Decimal
from unittest.mock import MagicMock, patch


# ── Config ──────────────────────────────────────────────────────────

class TestPremineConfig:
    """Verify GENESIS_PREMINE constant and related validation."""

    def test_premine_constant_exists(self):
        from qubitcoin.config import Config
        assert hasattr(Config, 'GENESIS_PREMINE')

    def test_premine_value(self):
        from qubitcoin.config import Config
        assert Config.GENESIS_PREMINE == Decimal('33000000')

    def test_premine_less_than_max_supply(self):
        from qubitcoin.config import Config
        assert Config.GENESIS_PREMINE < Config.MAX_SUPPLY

    def test_premine_non_negative(self):
        from qubitcoin.config import Config
        assert Config.GENESIS_PREMINE >= 0

    def test_premine_approximately_one_percent(self):
        from qubitcoin.config import Config
        pct = float(Config.GENESIS_PREMINE / Config.MAX_SUPPLY * 100)
        assert 0.9 < pct < 1.1  # ~1%

    def test_emission_schedule_valid_with_premine(self):
        from qubitcoin.config import Config
        assert Config.verify_emission_schedule() is True

    def test_premine_plus_phi_halving_under_cap(self):
        """Phi-halving emission (premine + mining) converges well under MAX_SUPPLY.

        The phi-halving series alone converges to ~651M QBC.  Tail emission
        fills the remaining ~2.65B up to MAX_SUPPLY over time.
        """
        from qubitcoin.config import Config
        PHI = Decimal(str(Config.PHI))
        total = Config.GENESIS_PREMINE
        for era in range(100):
            reward = Config.INITIAL_REWARD / (PHI ** era)
            if reward < Decimal('0.00000001'):
                break
            total += reward * Config.HALVING_INTERVAL
        assert total <= Config.MAX_SUPPLY

    def test_display_includes_premine(self):
        from qubitcoin.config import Config
        output = Config.display()
        assert 'Genesis Premine' in output
        assert '33,000,000' in output


# ── Coinbase Construction ───────────────────────────────────────────

class TestPremineCoinbase:
    """Verify MiningEngine._create_coinbase adds premine output at genesis."""

    def _make_engine(self):
        from qubitcoin.mining.engine import MiningEngine
        qe = MagicMock()
        ce = MagicMock()
        db = MagicMock()
        console = MagicMock()
        return MiningEngine(qe, ce, db, console)

    def test_genesis_coinbase_has_two_outputs(self):
        from qubitcoin.config import Config
        eng = self._make_engine()
        cb = eng._create_coinbase(
            height=0,
            reward=Config.INITIAL_REWARD,
            pending_txs=[],
            prev_hash='0' * 64,
        )
        assert len(cb.outputs) == 2

    def test_genesis_output_0_is_reward(self):
        from qubitcoin.config import Config
        eng = self._make_engine()
        cb = eng._create_coinbase(0, Config.INITIAL_REWARD, [], '0' * 64)
        assert cb.outputs[0]['amount'] == Config.INITIAL_REWARD

    def test_genesis_output_1_is_premine(self):
        from qubitcoin.config import Config
        eng = self._make_engine()
        cb = eng._create_coinbase(0, Config.INITIAL_REWARD, [], '0' * 64)
        assert cb.outputs[1]['amount'] == Config.GENESIS_PREMINE

    def test_genesis_total_amount(self):
        from qubitcoin.config import Config
        eng = self._make_engine()
        cb = eng._create_coinbase(0, Config.INITIAL_REWARD, [], '0' * 64)
        total = sum(Decimal(str(o['amount'])) for o in cb.outputs)
        assert total == Config.INITIAL_REWARD + Config.GENESIS_PREMINE

    def test_non_genesis_has_one_output(self):
        from qubitcoin.config import Config
        eng = self._make_engine()
        cb = eng._create_coinbase(1, Config.INITIAL_REWARD, [], 'a' * 64)
        assert len(cb.outputs) == 1

    def test_non_genesis_no_premine(self):
        from qubitcoin.config import Config
        eng = self._make_engine()
        cb = eng._create_coinbase(1, Config.INITIAL_REWARD, [], 'a' * 64)
        total = sum(Decimal(str(o['amount'])) for o in cb.outputs)
        assert total == Config.INITIAL_REWARD


# ── Consensus Validation ───────────────────────────────────────────

class TestPremineConsensus:
    """Verify consensus engine accepts premine at genesis, rejects elsewhere."""

    def _make_engine(self):
        from qubitcoin.consensus.engine import ConsensusEngine
        qe = MagicMock()
        qe.validate_proof.return_value = (True, "Valid")
        db = MagicMock()
        p2p = MagicMock()
        return ConsensusEngine(qe, db, p2p)

    def test_genesis_with_premine_valid(self):
        from qubitcoin.config import Config
        from qubitcoin.database.models import Block, Transaction
        eng = self._make_engine()
        db = MagicMock()
        db.get_total_supply.return_value = Decimal(0)
        eng.calculate_difficulty = MagicMock(return_value=1.0)

        coinbase = Transaction(
            txid='cb0', inputs=[],
            outputs=[
                {'address': 'miner', 'amount': Config.INITIAL_REWARD},
                {'address': 'miner', 'amount': Config.GENESIS_PREMINE},
            ],
            fee=Decimal(0), signature='', public_key='bb' * 64,
            timestamp=1000,
        )
        block = Block(
            height=0, block_hash=None, prev_hash='0' * 64,
            timestamp=1000, difficulty=1.0,
            proof_data={'params': [], 'challenge': [], 'energy': 0.5},
            transactions=[coinbase],
        )
        valid, reason = eng.validate_block(block, None, db)
        assert valid is True, f"Should accept genesis premine: {reason}"

    @patch('qubitcoin.consensus.engine.DilithiumSigner')
    def test_non_genesis_premine_rejected(self, mock_dil):
        mock_dil.verify.return_value = True
        from qubitcoin.config import Config
        from qubitcoin.database.models import Block, Transaction
        eng = self._make_engine()
        db = MagicMock()
        db.get_total_supply.return_value = Decimal(0)
        eng.calculate_difficulty = MagicMock(return_value=1.0)

        prev = Block(height=0, block_hash='a' * 64, prev_hash='0' * 64,
                     timestamp=1000, difficulty=1.0, proof_data={}, transactions=[])
        coinbase = Transaction(
            txid='cb1', inputs=[],
            outputs=[
                {'address': 'miner', 'amount': Config.INITIAL_REWARD},
                {'address': 'miner', 'amount': Config.GENESIS_PREMINE},
            ],
            fee=Decimal(0), signature='', public_key='bb' * 64,
            timestamp=1001,
        )
        block = Block(
            height=1, block_hash=None, prev_hash='a' * 64,
            timestamp=1001, difficulty=1.0,
            proof_data={'params': [], 'challenge': [], 'energy': 0.5,
                       'signature': 'aa' * 64, 'public_key': 'bb' * 64},
            transactions=[coinbase],
        )
        valid, reason = eng.validate_block(block, prev, db)
        assert valid is False
        assert 'coinbase' in reason.lower()


# ── Circulation Tracking ───────────────────────────────────────────

class TestPremineCirculation:
    """Verify CirculationTracker includes premine in emission calculations."""

    def test_emitted_at_genesis_includes_premine(self):
        from qubitcoin.config import Config
        from qubitcoin.aether.circulation import CirculationTracker
        total = CirculationTracker.compute_total_emitted(0)
        assert total == Config.INITIAL_REWARD + Config.GENESIS_PREMINE

    def test_emitted_at_height_10_includes_premine(self):
        from qubitcoin.config import Config
        from qubitcoin.aether.circulation import CirculationTracker
        total = CirculationTracker.compute_total_emitted(9)
        expected = Config.INITIAL_REWARD * 10 + Config.GENESIS_PREMINE
        assert total == expected

    def test_emitted_capped_at_max_supply(self):
        from qubitcoin.config import Config
        from qubitcoin.aether.circulation import CirculationTracker
        total = CirculationTracker.compute_total_emitted(999_999_999)
        assert total <= Config.MAX_SUPPLY

    def test_negative_height_no_premine(self):
        from qubitcoin.aether.circulation import CirculationTracker
        total = CirculationTracker.compute_total_emitted(-1)
        assert total == Decimal('0')
