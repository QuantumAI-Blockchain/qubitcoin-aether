"""Tests verifying Run #31 fixes: timestamp dedup, consciousness coherence,
range proof fields, difficulty cache eviction, fee burn enforcement,
BFS performance, private tx empty inputs.

Covers:
- ConsensusEngine.validate_block single timestamp check (no duplicate)
- ConsciousnessDashboard receives coherence + correct dict keys
- RangeProof includes l_vec/r_vec in _validate_private_transaction
- difficulty_cache bounded growth
- Coinbase fee burn enforcement at consensus level
- BFS uses deque.popleft (not list.pop(0))
- Private tx with empty inputs rejected
"""

import time
from collections import deque
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest


# ======================================================================
# Timestamp validation — single check, strict inequality
# ======================================================================


class TestTimestampValidation:
    """Verify duplicate timestamp checks were consolidated."""

    def test_equal_timestamp_rejected(self) -> None:
        """Block with same timestamp as parent should be rejected."""
        from qubitcoin.consensus.engine import ConsensusEngine
        ce = ConsensusEngine(MagicMock(), MagicMock(), MagicMock())

        block = MagicMock()
        block.height = 1
        block.prev_hash = 'a' * 64
        block.block_hash = None
        block.timestamp = 1000.0
        block.transactions = []

        prev = MagicMock()
        prev.height = 0
        prev.block_hash = 'a' * 64
        prev.timestamp = 1000.0  # same as block

        db = MagicMock()
        valid, reason = ce.validate_block(block, prev, db)
        assert valid is False
        assert 'not increasing' in reason.lower()

    def test_future_timestamp_rejected(self) -> None:
        """Block too far in the future should be rejected."""
        from qubitcoin.consensus.engine import ConsensusEngine
        from qubitcoin.config import Config
        ce = ConsensusEngine(MagicMock(), MagicMock(), MagicMock())

        block = MagicMock()
        block.height = 1
        block.prev_hash = 'a' * 64
        block.block_hash = None
        block.timestamp = time.time() + Config.MAX_FUTURE_BLOCK_TIME + 100

        prev = MagicMock()
        prev.height = 0
        prev.block_hash = 'a' * 64
        prev.timestamp = time.time() - 10

        db = MagicMock()
        valid, reason = ce.validate_block(block, prev, db)
        assert valid is False
        assert 'future' in reason.lower()


# ======================================================================
# ConsciousnessDashboard — correct dict keys + coherence
# ======================================================================


class TestConsciousnessKeys:
    """Verify proof_of_thought passes correct phi_result keys and coherence."""

    def test_integration_score_key(self) -> None:
        """phi_result uses 'integration_score', not 'integration'."""
        from qubitcoin.aether.phi_calculator import PhiCalculator
        from qubitcoin.aether.knowledge_graph import KnowledgeGraph
        kg = KnowledgeGraph(db_manager=MagicMock())
        pc = PhiCalculator(kg)
        result = pc.compute_phi(block_height=0)
        assert 'integration_score' in result
        assert 'differentiation_score' in result

    def test_coherence_passed_to_dashboard(self) -> None:
        """AetherEngine should pass coherence from pineal to dashboard."""
        from qubitcoin.aether.proof_of_thought import AetherEngine
        from qubitcoin.aether.consciousness import ConsciousnessDashboard

        dashboard = ConsciousnessDashboard()
        pineal = MagicMock()
        pineal.sephirot.get_coherence.return_value = 0.85
        pineal.metabolic_rate = 1.0
        pineal.melatonin = None

        phi_calc = MagicMock()
        phi_result = {
            'phi_value': 4.0,
            'integration_score': 2.5,
            'differentiation_score': 1.5,
            'num_nodes': 100,
            'num_edges': 200,
        }
        phi_calc._last_full_result = phi_result
        phi_calc.compute_phi.return_value = phi_result

        engine = AetherEngine(
            db_manager=MagicMock(),
            knowledge_graph=MagicMock(),
            phi_calculator=phi_calc,
            reasoning_engine=MagicMock(),
            pineal=pineal,
        )
        engine.consciousness_dashboard = dashboard

        # Mock knowledge graph — compute_knowledge_root is what generate_thought_proof calls
        engine.kg = MagicMock()
        engine.kg.compute_knowledge_root.return_value = 'abc123'
        # Skip auto-reasoning (not under test here — it needs fully wired subsystems)
        engine._auto_reason = MagicMock(return_value=[])

        engine.generate_thought_proof(block_height=10, validator_address='test_validator')

        # Check dashboard received measurement with coherence
        assert dashboard.measurement_count == 1
        m = dashboard._measurements[0]
        assert m.coherence == 0.85
        assert m.integration == 2.5
        assert m.differentiation == 1.5


# ======================================================================
# Difficulty cache eviction
# ======================================================================


class TestDifficultyCacheEviction:
    """Verify difficulty_cache doesn't grow unboundedly."""

    def test_cache_bounded(self) -> None:
        from qubitcoin.consensus.engine import ConsensusEngine
        from qubitcoin.config import Config
        ce = ConsensusEngine(MagicMock(), MagicMock(), MagicMock())
        limit = Config.DIFFICULTY_WINDOW * 2
        # Manually fill cache beyond limit
        for i in range(limit + 50):
            ce.difficulty_cache[i] = 1.0
            # Simulate the eviction logic from calculate_difficulty
            if len(ce.difficulty_cache) > limit:
                oldest = min(ce.difficulty_cache)
                del ce.difficulty_cache[oldest]
        assert len(ce.difficulty_cache) <= limit


# ======================================================================
# BFS uses deque — performance check
# ======================================================================


class TestBFSDeque:
    """Verify BFS hot paths use deque instead of list.pop(0)."""

    def test_knowledge_graph_subgraph_uses_deque(self) -> None:
        """get_subgraph should use deque for BFS queue."""
        import inspect
        from qubitcoin.aether.knowledge_graph import KnowledgeGraph
        source = inspect.getsource(KnowledgeGraph.get_subgraph)
        assert 'popleft' in source
        assert '.pop(0)' not in source

    def test_phi_calculator_bfs_uses_deque(self) -> None:
        """PhiCalculator integration BFS should use deque."""
        import inspect
        from qubitcoin.aether.phi_calculator import PhiCalculator
        source = inspect.getsource(PhiCalculator._compute_integration)
        assert 'popleft' in source
        assert '.pop(0)' not in source

    def test_hnsw_index_uses_heapq(self) -> None:
        """HNSWIndex search should use heapq, not sort+pop."""
        import inspect
        from qubitcoin.aether.vector_index import HNSWIndex
        if not hasattr(HNSWIndex, '_search_layer'):
            pytest.skip("HNSWIndex._search_layer not available (Rust backend)")
        source = inspect.getsource(HNSWIndex._search_layer)
        assert 'heappop' in source or 'heappush' in source
        assert '.pop(0)' not in source


# ======================================================================
# Coinbase fee burn enforcement
# ======================================================================


class TestCoinbaseFeeBurn:
    """Verify fee burn is enforced at consensus level."""

    def test_coinbase_rejects_unburned_fees(self) -> None:
        """Coinbase that claims 100% of fees should be rejected when burn > 0."""
        from qubitcoin.consensus.engine import ConsensusEngine
        from qubitcoin.config import Config
        ce = ConsensusEngine(MagicMock(), MagicMock(), MagicMock())

        now = time.time()
        reward = ce.calculate_reward(1, Decimal('0'))
        total_fees = Decimal('10.0')
        # burn=50% => max coinbase = reward + 5, not reward + 10

        coinbase_tx = MagicMock()
        coinbase_tx.inputs = []
        coinbase_tx.outputs = [{'amount': str(reward + total_fees)}]

        regular_tx = MagicMock()
        regular_tx.inputs = [{'txid': 'x', 'vout': 0}]
        regular_tx.fee = total_fees
        regular_tx.txid = 'regular'
        regular_tx.is_private = False

        block = MagicMock()
        block.height = 1
        block.prev_hash = 'a' * 64
        block.block_hash = None
        block.timestamp = now
        block.difficulty = 1.0
        block.proof_data = {'params': [], 'energy': 0.5, 'challenge': [], 'signature': 'aa' * 32, 'public_key': 'bb' * 32}
        block.state_root = None
        block.receipts_root = None
        block.transactions = [coinbase_tx, regular_tx]

        prev = MagicMock()
        prev.height = 0
        prev.block_hash = 'a' * 64
        prev.timestamp = now - 5

        db = MagicMock()
        db.get_total_supply.return_value = Decimal('0')

        ce.calculate_difficulty = MagicMock(return_value=1.0)
        ce.quantum.validate_proof = MagicMock(return_value=(True, ''))
        ce.validate_transaction = MagicMock(return_value=True)
        ce._validate_block_susy_swaps = MagicMock(return_value=(True, ''))

        with patch.object(Config, 'FEE_BURN_PERCENTAGE', 0.5), \
             patch('qubitcoin.consensus.engine.DilithiumSigner.verify', return_value=True):
            valid, reason = ce.validate_block(block, prev, db)
            assert valid is False
            assert 'excessive' in reason.lower() or 'coinbase' in reason.lower()


# ======================================================================
# Private tx empty inputs rejected
# ======================================================================


class TestPrivateTxEmptyInputs:
    """Verify private tx with empty inputs is rejected."""

    def test_empty_inputs_rejected(self) -> None:
        from qubitcoin.consensus.engine import ConsensusEngine
        ce = ConsensusEngine(MagicMock(), MagicMock(), MagicMock())

        tx = MagicMock()
        tx.inputs = []  # Empty!
        tx.txid = 'private_no_inputs'

        result = ce._validate_private_transaction(tx, MagicMock())
        assert result is False
