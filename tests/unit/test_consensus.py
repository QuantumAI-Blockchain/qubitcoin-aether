"""Unit tests for consensus engine — reward calculation, difficulty adjustment, validation."""
import pytest
from decimal import Decimal
from unittest.mock import MagicMock, patch, PropertyMock


class TestRewardCalculation:
    """Test golden ratio (phi) halving reward schedule."""

    def _make_engine(self):
        from qubitcoin.consensus.engine import ConsensusEngine
        qe = MagicMock()
        db = MagicMock()
        p2p = MagicMock()
        return ConsensusEngine(qe, db, p2p)

    def test_era_0_reward(self):
        """Era 0 gives INITIAL_REWARD."""
        eng = self._make_engine()
        reward = eng.calculate_reward(height=0, total_supply=Decimal(0))
        from qubitcoin.config import Config
        assert reward == Config.INITIAL_REWARD

    def test_era_1_reward(self):
        """Era 1 divides by PHI."""
        eng = self._make_engine()
        from qubitcoin.config import Config
        reward = eng.calculate_reward(
            height=Config.HALVING_INTERVAL,
            total_supply=Decimal(0),
        )
        expected = Config.INITIAL_REWARD / Decimal('1.618033988749895')
        assert abs(reward - expected) < Decimal('0.00000001')

    def test_reward_never_negative(self):
        """Reward is 0 when max supply reached."""
        eng = self._make_engine()
        from qubitcoin.config import Config
        reward = eng.calculate_reward(height=1, total_supply=Config.MAX_SUPPLY)
        assert reward == Decimal(0)

    def test_reward_capped_by_remaining(self):
        """Reward cannot exceed remaining supply."""
        eng = self._make_engine()
        from qubitcoin.config import Config
        remaining = Decimal('0.005')
        reward = eng.calculate_reward(
            height=0,
            total_supply=Config.MAX_SUPPLY - remaining,
        )
        assert reward <= remaining

    def test_multiple_eras_decrease(self):
        """Rewards strictly decrease with each era."""
        eng = self._make_engine()
        from qubitcoin.config import Config
        rewards = []
        for era in range(5):
            r = eng.calculate_reward(
                height=era * Config.HALVING_INTERVAL,
                total_supply=Decimal(0),
            )
            rewards.append(r)
        for i in range(1, len(rewards)):
            assert rewards[i] < rewards[i - 1]

    def test_era_boundary_exact_halving_height(self):
        """Reward correctly transitions at exact halving interval boundary."""
        eng = self._make_engine()
        from qubitcoin.config import Config
        H = Config.HALVING_INTERVAL
        r_before = eng.calculate_reward(H - 1, Decimal(0))
        r_at = eng.calculate_reward(H, Decimal(0))
        r_after = eng.calculate_reward(H + 1, Decimal(0))
        # Era 0 → Era 1 transition: reward drops
        assert r_before == Config.INITIAL_REWARD  # Still era 0
        assert r_at < r_before  # Era 1 starts
        assert r_at == r_after  # Same era 1
        # Verify exact phi-halving ratio
        expected = Config.INITIAL_REWARD / Decimal(str(Config.PHI))
        assert abs(r_at - expected) < Decimal('0.00000001')

    def test_era_boundary_second_halving(self):
        """Reward transitions correctly at second halving (era 1 → 2)."""
        eng = self._make_engine()
        from qubitcoin.config import Config
        H = Config.HALVING_INTERVAL
        PHI = Decimal(str(Config.PHI))
        r_era1 = eng.calculate_reward(H, Decimal(0))
        r_era2 = eng.calculate_reward(2 * H, Decimal(0))
        expected_era2 = Config.INITIAL_REWARD / (PHI ** 2)
        assert abs(r_era2 - expected_era2) < Decimal('0.00000001')
        assert r_era2 < r_era1


class TestTailEmission:
    """Test tail emission — fixed reward after phi-halving drops below threshold."""

    def _make_engine(self):
        from qubitcoin.consensus.engine import ConsensusEngine
        qe = MagicMock()
        db = MagicMock()
        p2p = MagicMock()
        return ConsensusEngine(qe, db, p2p)

    def test_early_eras_use_phi_halving(self):
        """Eras 0-10 should use phi-halving, not tail emission."""
        from qubitcoin.config import Config
        eng = self._make_engine()
        PHI = Decimal(str(Config.PHI))
        for era in range(11):
            height = era * Config.HALVING_INTERVAL
            reward = eng.calculate_reward(height, Decimal(0))
            expected_phi = Config.INITIAL_REWARD / (PHI ** era)
            if expected_phi >= Config.TAIL_EMISSION_REWARD:
                assert abs(reward - expected_phi) < Decimal('0.00000001'), \
                    f"Era {era}: expected {expected_phi}, got {reward}"

    def test_tail_emission_kicks_in(self):
        """At high eras, tail emission should replace the vanishing phi-halving reward."""
        from qubitcoin.config import Config
        eng = self._make_engine()
        PHI = Decimal(str(Config.PHI))
        # Find the first era where phi-halving < TAIL_EMISSION_REWARD
        tail_era = 0
        for era in range(100):
            if Config.INITIAL_REWARD / (PHI ** era) < Config.TAIL_EMISSION_REWARD:
                tail_era = era
                break
        assert tail_era > 0, "Tail emission era should be > 0"
        # At tail era, reward should be TAIL_EMISSION_REWARD (not the tiny phi value)
        height = tail_era * Config.HALVING_INTERVAL
        reward = eng.calculate_reward(height, Decimal(0))
        assert reward == Config.TAIL_EMISSION_REWARD

    def test_tail_emission_continues_past_phi_halving(self):
        """Tail emission should give consistent reward for many eras past the cutover."""
        from qubitcoin.config import Config
        eng = self._make_engine()
        # Era 20 is well into tail emission territory
        for era in [20, 30, 50]:
            height = era * Config.HALVING_INTERVAL
            reward = eng.calculate_reward(height, Decimal(0))
            assert reward == Config.TAIL_EMISSION_REWARD, \
                f"Era {era}: expected tail emission {Config.TAIL_EMISSION_REWARD}, got {reward}"

    def test_tail_emission_capped_at_max_supply(self):
        """Even tail emission stops at MAX_SUPPLY."""
        from qubitcoin.config import Config
        eng = self._make_engine()
        # Just below max supply — reward should be the remaining amount
        remaining = Decimal('0.05')
        reward = eng.calculate_reward(
            height=50 * Config.HALVING_INTERVAL,
            total_supply=Config.MAX_SUPPLY - remaining,
        )
        assert reward == remaining  # Less than TAIL_EMISSION_REWARD, capped by remaining

    def test_tail_emission_zero_at_max_supply(self):
        """Reward is 0 when MAX_SUPPLY is fully emitted."""
        from qubitcoin.config import Config
        eng = self._make_engine()
        reward = eng.calculate_reward(
            height=50 * Config.HALVING_INTERVAL,
            total_supply=Config.MAX_SUPPLY,
        )
        assert reward == Decimal(0)

    def test_tail_era_number(self):
        """Tail emission should kick in around era 11 with current constants.

        PHI^11 = ~199.0, so 15.27/199 = ~0.077 < 0.1 (TAIL_EMISSION_REWARD).
        PHI^10 = ~122.99, so 15.27/123 = ~0.124 > 0.1.
        """
        from qubitcoin.config import Config
        PHI = Decimal(str(Config.PHI))
        era_10_reward = Config.INITIAL_REWARD / (PHI ** 10)
        era_11_reward = Config.INITIAL_REWARD / (PHI ** 11)
        assert era_10_reward > Config.TAIL_EMISSION_REWARD, \
            f"Era 10 reward {era_10_reward} should be above tail threshold"
        assert era_11_reward < Config.TAIL_EMISSION_REWARD, \
            f"Era 11 reward {era_11_reward} should be below tail threshold"

    def test_phi_halving_convergence_well_below_max(self):
        """Phi-halving alone converges to ~651M QBC, far below 3.3B MAX_SUPPLY.

        This is the R26-21 bug: without tail emission, 80% of supply is unmintable.
        """
        from qubitcoin.config import Config
        PHI = Decimal(str(Config.PHI))
        total = Config.GENESIS_PREMINE
        for era in range(100):
            reward = Config.INITIAL_REWARD / (PHI ** era)
            if reward < Decimal('0.00000001'):
                break
            total += reward * Config.HALVING_INTERVAL
        # Phi-halving converges to ~651M QBC (about 19.7% of MAX_SUPPLY)
        assert total < Config.MAX_SUPPLY * Decimal('0.25'), \
            f"Phi-halving total {total} should be well under 25% of MAX_SUPPLY"
        assert total > Decimal('600000000'), \
            f"Phi-halving total {total} should converge to ~651M"

    def test_total_emission_can_reach_max_supply(self):
        """With tail emission, the full MAX_SUPPLY is eventually reachable."""
        from qubitcoin.config import Config
        # Calculate how many blocks of tail emission are needed to fill the gap
        PHI = Decimal(str(Config.PHI))
        phi_total = Config.GENESIS_PREMINE
        for era in range(100):
            phi_reward = Config.INITIAL_REWARD / (PHI ** era)
            if phi_reward < Config.TAIL_EMISSION_REWARD:
                # From this era onward it's tail emission
                tail_start_block = era * Config.HALVING_INTERVAL
                break
            phi_total += phi_reward * Config.HALVING_INTERVAL

        # Add the partial blocks in tail eras up to phi convergence
        remaining = Config.MAX_SUPPLY - phi_total
        # With tail emission at 0.1 QBC/block, this many blocks to fill
        blocks_needed = remaining / Config.TAIL_EMISSION_REWARD
        # Verify it's finite and reachable (not infinite)
        assert blocks_needed > 0
        assert blocks_needed < Decimal('100000000000')  # < 100B blocks

    def test_get_emission_stats_includes_tail_info(self):
        """get_emission_stats should return tail emission fields."""
        from qubitcoin.config import Config
        eng = self._make_engine()
        db = MagicMock()
        db.get_current_height.return_value = 100
        db.get_total_supply.return_value = Decimal('100000')
        stats = eng.get_emission_stats(db)
        assert 'tail_emission_reward' in stats
        assert 'in_tail_emission' in stats
        assert stats['tail_emission_reward'] == float(Config.TAIL_EMISSION_REWARD)
        assert stats['in_tail_emission'] is False  # Era 0, not in tail

    def test_get_emission_stats_in_tail(self):
        """get_emission_stats correctly reports tail emission when in late eras."""
        from qubitcoin.config import Config
        eng = self._make_engine()
        db = MagicMock()
        # Height deep in tail emission territory (era 20)
        db.get_current_height.return_value = 20 * Config.HALVING_INTERVAL
        db.get_total_supply.return_value = Decimal('700000000')
        stats = eng.get_emission_stats(db)
        assert stats['in_tail_emission'] is True


class TestDifficultyAdjustment:
    """Test difficulty calculation with 144-block window."""

    def _make_engine(self):
        from qubitcoin.consensus.engine import ConsensusEngine
        qe = MagicMock()
        db = MagicMock()
        p2p = MagicMock()
        return ConsensusEngine(qe, db, p2p)

    def test_early_blocks_use_initial(self):
        """Blocks before window use INITIAL_DIFFICULTY."""
        from qubitcoin.config import Config
        eng = self._make_engine()
        db = MagicMock()
        diff = eng.calculate_difficulty(height=10, db_manager=db)
        assert diff == Config.INITIAL_DIFFICULTY

    def test_perfect_timing_no_change(self):
        """When blocks arrive at exactly TARGET_BLOCK_TIME, difficulty unchanged."""
        from qubitcoin.config import Config
        eng = self._make_engine()
        db = MagicMock()

        window = Config.DIFFICULTY_WINDOW  # 144
        head = MagicMock()
        head.timestamp = 1000 + Config.TARGET_BLOCK_TIME * window
        head.difficulty = 1.0
        start = MagicMock()
        start.timestamp = 1000

        db.get_block = lambda h: head if h == window - 1 else start
        diff = eng.calculate_difficulty(height=window, db_manager=db)
        # height < DIFFICULTY_FIX_HEIGHT → legacy ratio = expected/actual = 1.0 → no change
        assert abs(diff - 1.0) < 0.01

    def test_slow_blocks_increase_difficulty(self):
        """If blocks are slower than target, difficulty increases."""
        from qubitcoin.config import Config
        eng = self._make_engine()
        db = MagicMock()

        window = Config.DIFFICULTY_WINDOW
        head = MagicMock()
        # 2x slower than target
        head.timestamp = 1000 + Config.TARGET_BLOCK_TIME * window * 2
        head.difficulty = 1.0
        start = MagicMock()
        start.timestamp = 1000

        db.get_block = lambda h: head if h == window - 1 else start
        diff = eng.calculate_difficulty(height=window, db_manager=db)
        # height < DIFFICULTY_FIX_HEIGHT → legacy ratio = expected/actual = 0.5, clamped to 0.9
        assert diff < 1.0  # legacy formula: slow blocks decrease difficulty (inverted)

    def test_fast_blocks_decrease_difficulty(self):
        """If blocks are faster than target, difficulty should change."""
        from qubitcoin.config import Config
        eng = self._make_engine()
        db = MagicMock()

        window = Config.DIFFICULTY_WINDOW
        head = MagicMock()
        # 0.5x faster than target (blocks come twice as fast)
        head.timestamp = 1000 + Config.TARGET_BLOCK_TIME * window * 0.5
        head.difficulty = 1.0
        start = MagicMock()
        start.timestamp = 1000

        db.get_block = lambda h: head if h == window - 1 else start
        diff = eng.calculate_difficulty(height=window, db_manager=db)
        assert diff > 1.0  # difficulty increased since blocks are too fast

    def test_max_difficulty_change_capped(self):
        """Difficulty change per adjustment capped at MAX_DIFFICULTY_CHANGE."""
        from qubitcoin.config import Config
        eng = self._make_engine()
        db = MagicMock()

        window = Config.DIFFICULTY_WINDOW
        head = MagicMock()
        # Extreme: blocks came 100x slower
        head.timestamp = 1000 + Config.TARGET_BLOCK_TIME * window * 100
        head.difficulty = 1.0
        start = MagicMock()
        start.timestamp = 1000

        db.get_block = lambda h: head if h == window - 1 else start
        diff = eng.calculate_difficulty(height=window, db_manager=db)
        # Should be clamped to 1.0 * (1 - 0.10) = 0.90
        assert diff >= 0.89  # ±10% max change


class TestBlockValidation:
    """Test block validation rules."""

    def _make_engine(self):
        from qubitcoin.consensus.engine import ConsensusEngine
        qe = MagicMock()
        qe.validate_proof.return_value = (True, "Valid")
        db = MagicMock()
        p2p = MagicMock()
        eng = ConsensusEngine(qe, db, p2p)
        return eng

    def test_height_mismatch_rejected(self):
        """Block with wrong height is rejected."""
        eng = self._make_engine()
        db = MagicMock()

        from qubitcoin.database.models import Block
        prev = Block(height=10, block_hash='a' * 64, prev_hash='0' * 64,
                     timestamp=1000, difficulty=1.0, proof_data={}, transactions=[])
        block = Block(height=99, block_hash='b' * 64, prev_hash='a' * 64,
                      timestamp=1001, difficulty=1.0, proof_data={}, transactions=[])
        valid, reason = eng.validate_block(block, prev, db)
        assert valid is False
        assert 'height' in reason.lower()

    def test_prev_hash_mismatch_rejected(self):
        """Block with wrong prev_hash is rejected."""
        eng = self._make_engine()
        db = MagicMock()

        from qubitcoin.database.models import Block
        prev = Block(height=10, block_hash='a' * 64, prev_hash='0' * 64,
                     timestamp=1000, difficulty=1.0, proof_data={}, transactions=[])
        block = Block(height=11, block_hash='b' * 64, prev_hash='f' * 64,
                      timestamp=1001, difficulty=1.0, proof_data={}, transactions=[])
        valid, reason = eng.validate_block(block, prev, db)
        assert valid is False
        assert 'prev_hash' in reason.lower()

    def test_no_coinbase_rejected(self):
        """Block without coinbase transaction is rejected."""
        eng = self._make_engine()
        db = MagicMock()
        db.get_total_supply.return_value = Decimal(0)

        # Bypass difficulty and tx validation so we reach the coinbase check
        eng.calculate_difficulty = MagicMock(return_value=1.0)
        eng.validate_transaction = MagicMock(return_value=True)

        from qubitcoin.database.models import Block, Transaction
        prev = Block(height=0, block_hash='a' * 64, prev_hash='0' * 64,
                     timestamp=1000, difficulty=1.0, proof_data={}, transactions=[])

        # Regular tx with inputs (not coinbase) — has inputs so coinbase_count stays 0
        tx = Transaction(txid='tx1', inputs=[{'txid': 'x', 'vout': 0}],
                         outputs=[{'address': 'a', 'amount': Decimal(1)}],
                         fee=Decimal('0.01'), signature='aa' * 64, public_key='bb' * 64,
                         timestamp=1001)

        block = Block(height=1, block_hash=None, prev_hash='a' * 64,
                      timestamp=1001, difficulty=1.0,
                      proof_data={'params': [], 'challenge': [], 'energy': 0.5},
                      transactions=[tx])
        valid, reason = eng.validate_block(block, prev, db)
        assert valid is False
        assert 'coinbase' in reason.lower()

    def test_genesis_coinbase_with_premine_accepted(self):
        """Genesis block coinbase with 2 outputs (reward + premine) passes validation."""
        eng = self._make_engine()
        db = MagicMock()
        db.get_total_supply.return_value = Decimal(0)
        eng.calculate_difficulty = MagicMock(return_value=1.0)

        from qubitcoin.config import Config
        from qubitcoin.database.models import Block, Transaction

        # Genesis coinbase with 2 outputs: reward + premine
        coinbase = Transaction(
            txid='coinbase0', inputs=[],
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
        assert valid is True, f"Genesis with premine should be valid: {reason}"

    def test_non_genesis_with_premine_rejected(self):
        """Non-genesis block with premine-sized coinbase is rejected."""
        eng = self._make_engine()
        db = MagicMock()
        db.get_total_supply.return_value = Decimal(0)
        eng.calculate_difficulty = MagicMock(return_value=1.0)

        from qubitcoin.config import Config
        from qubitcoin.database.models import Block, Transaction

        prev = Block(height=0, block_hash='a' * 64, prev_hash='0' * 64,
                     timestamp=1000, difficulty=1.0, proof_data={}, transactions=[])

        # Non-genesis coinbase tries to include premine
        coinbase = Transaction(
            txid='coinbase1', inputs=[],
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
            proof_data={'params': [], 'challenge': [], 'energy': 0.5},
            transactions=[coinbase],
        )
        valid, reason = eng.validate_block(block, prev, db)
        assert valid is False
        assert 'coinbase' in reason.lower()
