"""
Performance benchmark suite for Qubitcoin core operations.

Measures wall-clock time for critical-path operations:
  - Block creation + validation
  - VQE mining attempts (single optimization)
  - Database queries (block lookup, UTXO, balance)
  - QVM execution (contract deploy + call)

All benchmarks are self-contained with mocked dependencies so they can
run without a live node, database, or quantum hardware.

Usage:
    pytest tests/benchmarks/bench_core.py -v -m benchmark
    pytest tests/benchmarks/bench_core.py -v -s   # with print output
"""

import hashlib
import json
import time
import statistics
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

# ─── Mark all tests in this module as benchmarks ────────────────────────────

pytestmark = pytest.mark.benchmark


# ─── Helpers ────────────────────────────────────────────────────────────────

def _format_table(rows: List[Tuple[str, str, str, str]]) -> str:
    """Format benchmark results as a table.

    Args:
        rows: List of (name, iterations, avg_ms, unit) tuples.

    Returns:
        Formatted table string.
    """
    header = ("Benchmark", "Iterations", "Avg Time", "Unit")
    col_widths = [
        max(len(header[i]), *(len(r[i]) for r in rows))
        for i in range(4)
    ]
    sep = "+" + "+".join("-" * (w + 2) for w in col_widths) + "+"
    fmt = "| " + " | ".join(f"{{:<{w}}}" for w in col_widths) + " |"

    lines = [sep, fmt.format(*header), sep]
    for row in rows:
        lines.append(fmt.format(*row))
    lines.append(sep)
    return "\n".join(lines)


def _make_mock_db() -> MagicMock:
    """Create a mock DatabaseManager with realistic return values."""
    db = MagicMock()
    db.get_current_height.return_value = 100
    db.get_total_supply.return_value = Decimal("1527000")
    db.get_pending_transactions.return_value = []

    # Build a realistic block for lookups
    mock_block = MagicMock()
    mock_block.height = 100
    mock_block.prev_hash = "a" * 64
    mock_block.block_hash = "b" * 64
    mock_block.timestamp = time.time() - 330.0  # ~100 blocks ago at 3.3s each
    mock_block.difficulty = 1.0
    mock_block.proof_data = {
        "params": [0.1] * 12,
        "energy": 0.5,
        "challenge": [("IIIZ", 0.3), ("ZZII", -0.5)],
    }
    mock_block.transactions = []
    mock_block.state_root = ""
    mock_block.receipts_root = ""
    mock_block.thought_proof = None
    mock_block.calculate_hash.return_value = "c" * 64

    def get_block(h: int) -> Optional[MagicMock]:
        if 0 <= h <= 100:
            b = MagicMock()
            b.height = h
            b.prev_hash = hashlib.sha256(str(h - 1).encode()).hexdigest() if h > 0 else "0" * 64
            b.block_hash = hashlib.sha256(str(h).encode()).hexdigest()
            b.timestamp = time.time() - (100 - h) * 3.3
            b.difficulty = 1.0
            b.proof_data = mock_block.proof_data
            b.transactions = []
            b.state_root = ""
            b.receipts_root = ""
            b.thought_proof = None
            return b
        return None

    db.get_block.side_effect = get_block

    # UTXO query mock — returns 10 UTXOs for any address
    from qubitcoin.database.models import UTXO
    db.get_utxos.return_value = [
        UTXO(
            txid=hashlib.sha256(f"tx{i}".encode()).hexdigest(),
            vout=0,
            amount=Decimal("15.27"),
            address="qbc1testaddr",
            proof={"energy": 0.5},
            block_height=i * 10,
            spent=False,
        )
        for i in range(10)
    ]

    # Balance query mock
    db.get_balance = MagicMock(return_value=Decimal("152.70"))

    # Contract bytecode mock (simple PUSH1 0 PUSH1 0 RETURN)
    db.get_contract_bytecode = MagicMock(return_value="600060006000f3")

    # Account mock
    from qubitcoin.database.models import Account
    db.get_or_create_account.return_value = Account(
        address="0x" + "a" * 40,
        nonce=0,
        balance=Decimal("1000"),
    )
    db.update_account = MagicMock()

    # Session context manager mock
    session_mock = MagicMock()
    session_mock.__enter__ = MagicMock(return_value=session_mock)
    session_mock.__exit__ = MagicMock(return_value=False)
    db.get_session.return_value = session_mock

    return db


def _make_quantum_engine() -> "QuantumEngine":
    """Create a real QuantumEngine (uses StatevectorEstimator — no hardware needed)."""
    from qubitcoin.quantum.engine import QuantumEngine
    return QuantumEngine()


# ─── Block Validation Benchmark ─────────────────────────────────────────────

class TestBlockValidationBenchmark:
    """Benchmark block creation and validation throughput."""

    def _make_engine(self) -> "ConsensusEngine":
        from qubitcoin.consensus.engine import ConsensusEngine
        qe = MagicMock()
        # validate_proof returns (True, "OK") for benchmarking
        qe.validate_proof.return_value = (True, "OK")
        qe.generate_hamiltonian.return_value = [("IIII", 0.1)]
        qe.compute_exact_ground_state.return_value = -0.5
        db = _make_mock_db()
        p2p = MagicMock()
        return ConsensusEngine(qe, db, p2p)

    def _make_block(self, height: int, prev_hash: str, difficulty: float) -> "Block":
        from qubitcoin.database.models import Block, Transaction
        coinbase = Transaction(
            txid=hashlib.sha256(f"cb{height}".encode()).hexdigest(),
            inputs=[],
            outputs=[{"address": "qbc1miner", "amount": Decimal("15.27")}],
            fee=Decimal(0),
            signature="",
            public_key="",
            timestamp=time.time(),
            block_height=height,
        )
        block = Block(
            height=height,
            prev_hash=prev_hash,
            proof_data={
                "params": [0.1] * 12,
                "energy": 0.5,
                "challenge": [("IIIZ", 0.3), ("ZZII", -0.5)],
                "public_key": "",
                "signature": "",
            },
            transactions=[coinbase],
            timestamp=time.time(),
            difficulty=difficulty,
        )
        block.block_hash = block.calculate_hash()
        return block

    def test_block_validation_speed(self) -> None:
        """Benchmark: create and validate 100 blocks, report avg time."""
        engine = self._make_engine()
        db = _make_mock_db()
        iterations = 100
        times: List[float] = []

        prev_hash = "0" * 64
        for i in range(iterations):
            block = self._make_block(i, prev_hash, 1.0)

            # Mock prev_block for validation
            prev_block = MagicMock()
            prev_block.height = i - 1
            prev_block.block_hash = prev_hash
            prev_block.timestamp = block.timestamp - 3.3

            start = time.perf_counter()
            valid, reason = engine.validate_block(
                block,
                prev_block if i > 0 else None,
                db,
            )
            elapsed = time.perf_counter() - start
            times.append(elapsed)
            prev_hash = block.block_hash

        avg_ms = statistics.mean(times) * 1000
        median_ms = statistics.median(times) * 1000
        p95_ms = sorted(times)[int(0.95 * len(times))] * 1000

        results = [
            ("Block validation (avg)", str(iterations), f"{avg_ms:.3f}", "ms"),
            ("Block validation (median)", str(iterations), f"{median_ms:.3f}", "ms"),
            ("Block validation (p95)", str(iterations), f"{p95_ms:.3f}", "ms"),
        ]
        print("\n" + _format_table(results))

        # Sanity: validation should be fast (<50ms per block without real quantum)
        assert avg_ms < 50.0, f"Block validation too slow: {avg_ms:.3f}ms avg"

    def test_block_hash_speed(self) -> None:
        """Benchmark: compute block hash for 1000 blocks."""
        from qubitcoin.database.models import Block, Transaction
        iterations = 1000
        times: List[float] = []

        for i in range(iterations):
            block = self._make_block(i, "0" * 64, 1.0)

            start = time.perf_counter()
            _ = block.calculate_hash()
            elapsed = time.perf_counter() - start
            times.append(elapsed)

        avg_us = statistics.mean(times) * 1_000_000
        print(f"\nBlock hash: {avg_us:.1f} us/block ({iterations} iterations)")
        assert avg_us < 5000, f"Block hash too slow: {avg_us:.1f}us"


# ─── VQE Mining Benchmark ───────────────────────────────────────────────────

class TestVQEMiningBenchmark:
    """Benchmark VQE optimization speed (the core mining operation)."""

    def test_single_vqe_optimization(self) -> None:
        """Benchmark: single VQE optimization (COBYLA on 4-qubit Hamiltonian)."""
        qe = _make_quantum_engine()
        iterations = 5  # VQE is slow (~1-3s each), keep count low

        hamiltonian = qe.generate_hamiltonian(seed=42)
        times: List[float] = []

        for i in range(iterations):
            start = time.perf_counter()
            params, energy = qe.optimize_vqe(hamiltonian)
            elapsed = time.perf_counter() - start
            times.append(elapsed)

        avg_s = statistics.mean(times)
        min_s = min(times)
        max_s = max(times)

        results = [
            ("VQE optimization (avg)", str(iterations), f"{avg_s:.3f}", "s"),
            ("VQE optimization (min)", str(iterations), f"{min_s:.3f}", "s"),
            ("VQE optimization (max)", str(iterations), f"{max_s:.3f}", "s"),
        ]
        print("\n" + _format_table(results))

        # VQE should complete within 30s per iteration on any modern CPU
        assert avg_s < 30.0, f"VQE optimization too slow: {avg_s:.3f}s avg"

    def test_hamiltonian_generation(self) -> None:
        """Benchmark: deterministic Hamiltonian generation."""
        qe = _make_quantum_engine()
        iterations = 1000
        times: List[float] = []

        for i in range(iterations):
            start = time.perf_counter()
            _ = qe.generate_hamiltonian(prev_hash="a" * 64, height=i)
            elapsed = time.perf_counter() - start
            times.append(elapsed)

        avg_us = statistics.mean(times) * 1_000_000
        print(f"\nHamiltonian generation: {avg_us:.1f} us/call ({iterations} iterations)")
        assert avg_us < 5000, f"Hamiltonian generation too slow: {avg_us:.1f}us"

    def test_energy_computation(self) -> None:
        """Benchmark: single energy computation (circuit simulation)."""
        qe = _make_quantum_engine()
        hamiltonian = qe.generate_hamiltonian(seed=42)
        import numpy as np
        ansatz = qe.create_ansatz()
        params = np.random.uniform(0, 2 * np.pi, ansatz.num_parameters)

        iterations = 20
        times: List[float] = []

        for _ in range(iterations):
            start = time.perf_counter()
            _ = qe.compute_energy(params, hamiltonian)
            elapsed = time.perf_counter() - start
            times.append(elapsed)

        avg_ms = statistics.mean(times) * 1000
        results = [
            ("Energy computation (avg)", str(iterations), f"{avg_ms:.3f}", "ms"),
        ]
        print("\n" + _format_table(results))
        assert avg_ms < 500.0, f"Energy computation too slow: {avg_ms:.3f}ms"


# ─── Database Query Benchmark ───────────────────────────────────────────────

class TestDatabaseQueryBenchmark:
    """Benchmark database query patterns (mocked — measures serialization overhead)."""

    def test_block_lookup_speed(self) -> None:
        """Benchmark: block lookup by height."""
        db = _make_mock_db()
        iterations = 10000
        times: List[float] = []

        for i in range(iterations):
            start = time.perf_counter()
            _ = db.get_block(i % 101)  # Heights 0-100
            elapsed = time.perf_counter() - start
            times.append(elapsed)

        avg_us = statistics.mean(times) * 1_000_000
        print(f"\nBlock lookup (mock): {avg_us:.2f} us/call ({iterations} iterations)")
        # Mock-only: should be very fast (<100us)
        assert avg_us < 1000, f"Block lookup too slow: {avg_us:.2f}us"

    def test_utxo_query_speed(self) -> None:
        """Benchmark: UTXO query for an address."""
        db = _make_mock_db()
        iterations = 10000
        times: List[float] = []

        for _ in range(iterations):
            start = time.perf_counter()
            utxos = db.get_utxos("qbc1testaddr")
            elapsed = time.perf_counter() - start
            times.append(elapsed)

        avg_us = statistics.mean(times) * 1_000_000
        print(f"\nUTXO query (mock): {avg_us:.2f} us/call ({iterations} iterations)")
        assert avg_us < 1000, f"UTXO query too slow: {avg_us:.2f}us"

    def test_balance_query_speed(self) -> None:
        """Benchmark: balance query for an address."""
        db = _make_mock_db()
        iterations = 10000
        times: List[float] = []

        for _ in range(iterations):
            start = time.perf_counter()
            _ = db.get_balance("qbc1testaddr")
            elapsed = time.perf_counter() - start
            times.append(elapsed)

        avg_us = statistics.mean(times) * 1_000_000
        print(f"\nBalance query (mock): {avg_us:.2f} us/call ({iterations} iterations)")
        assert avg_us < 1000, f"Balance query too slow: {avg_us:.2f}us"

    def test_utxo_model_serialization(self) -> None:
        """Benchmark: UTXO dataclass to_dict/from_dict round-trip."""
        from qubitcoin.database.models import UTXO
        utxo = UTXO(
            txid="a" * 64,
            vout=0,
            amount=Decimal("15.27"),
            address="qbc1testaddr",
            proof={"energy": 0.5, "params": [0.1] * 12},
            block_height=100,
            spent=False,
        )
        iterations = 10000
        times: List[float] = []

        for _ in range(iterations):
            start = time.perf_counter()
            d = utxo.to_dict()
            _ = UTXO.from_dict(d)
            elapsed = time.perf_counter() - start
            times.append(elapsed)

        avg_us = statistics.mean(times) * 1_000_000
        print(f"\nUTXO round-trip: {avg_us:.2f} us/call ({iterations} iterations)")
        assert avg_us < 1000, f"UTXO round-trip too slow: {avg_us:.2f}us"

    def test_transaction_serialization(self) -> None:
        """Benchmark: Transaction dataclass to_dict/from_dict round-trip."""
        from qubitcoin.database.models import Transaction
        tx = Transaction(
            txid="b" * 64,
            inputs=[{"txid": "a" * 64, "vout": 0}],
            outputs=[{"address": "qbc1recv", "amount": Decimal("10.00")}],
            fee=Decimal("0.0001"),
            signature="sig" * 20,
            public_key="pk" * 20,
            timestamp=time.time(),
        )
        iterations = 10000
        times: List[float] = []

        for _ in range(iterations):
            start = time.perf_counter()
            d = tx.to_dict()
            _ = Transaction.from_dict(d)
            elapsed = time.perf_counter() - start
            times.append(elapsed)

        avg_us = statistics.mean(times) * 1_000_000
        print(f"\nTransaction round-trip: {avg_us:.2f} us/call ({iterations} iterations)")
        assert avg_us < 2000, f"Transaction round-trip too slow: {avg_us:.2f}us"


# ─── QVM Execution Benchmark ────────────────────────────────────────────────

class TestQVMExecutionBenchmark:
    """Benchmark QVM bytecode execution speed."""

    def _make_qvm(self) -> "QVM":
        from qubitcoin.qvm.vm import QVM
        db = _make_mock_db()
        return QVM(db, quantum_engine=None, compliance_engine=None)

    def test_simple_contract_deploy(self) -> None:
        """Benchmark: deploy a minimal contract (PUSH1 0x42, PUSH1 0, MSTORE, PUSH1 32, PUSH1 0, RETURN).

        Init code stores a single value and returns it as runtime bytecode.
        """
        qvm = self._make_qvm()

        # Init code: PUSH1 0x42, PUSH1 0, MSTORE, PUSH1 32, PUSH1 0, RETURN
        # This stores 0x42 at memory[0] and returns 32 bytes as runtime code.
        init_code = bytes([
            0x60, 0x42,  # PUSH1 0x42
            0x60, 0x00,  # PUSH1 0
            0x52,        # MSTORE
            0x60, 0x20,  # PUSH1 32
            0x60, 0x00,  # PUSH1 0
            0xf3,        # RETURN
        ])

        iterations = 100
        times: List[float] = []

        for i in range(iterations):
            start = time.perf_counter()
            result = qvm.execute(
                caller="0x" + "a" * 40,
                address="0x" + hashlib.sha256(str(i).encode()).hexdigest()[:40],
                code=init_code,
                data=b"",
                value=0,
                gas=1_000_000,
            )
            elapsed = time.perf_counter() - start
            times.append(elapsed)

        avg_ms = statistics.mean(times) * 1000
        results = [
            ("Contract deploy (avg)", str(iterations), f"{avg_ms:.3f}", "ms"),
        ]
        print("\n" + _format_table(results))
        assert avg_ms < 100.0, f"Contract deploy too slow: {avg_ms:.3f}ms"

    def test_simple_arithmetic_execution(self) -> None:
        """Benchmark: execute arithmetic bytecode (ADD, MUL, SUB loop)."""
        qvm = self._make_qvm()

        # Bytecode: PUSH1 10, PUSH1 20, ADD, PUSH1 3, MUL, PUSH1 1, SUB, STOP
        code = bytes([
            0x60, 0x0a,  # PUSH1 10
            0x60, 0x14,  # PUSH1 20
            0x01,        # ADD -> 30
            0x60, 0x03,  # PUSH1 3
            0x02,        # MUL -> 90
            0x60, 0x01,  # PUSH1 1
            0x03,        # SUB -> 89
            0x00,        # STOP
        ])

        iterations = 1000
        times: List[float] = []

        for _ in range(iterations):
            start = time.perf_counter()
            result = qvm.execute(
                caller="0x" + "a" * 40,
                address="0x" + "b" * 40,
                code=code,
                gas=100_000,
            )
            elapsed = time.perf_counter() - start
            times.append(elapsed)
            assert result.success, f"Execution failed: {result.revert_reason}"

        avg_us = statistics.mean(times) * 1_000_000
        results = [
            ("Arithmetic execution (avg)", str(iterations), f"{avg_us:.1f}", "us"),
        ]
        print("\n" + _format_table(results))
        assert avg_us < 10_000, f"Arithmetic execution too slow: {avg_us:.1f}us"

    def test_memory_operations(self) -> None:
        """Benchmark: MSTORE + MLOAD cycle."""
        qvm = self._make_qvm()

        # Store value to memory, load it back, stop
        code = bytes([
            0x60, 0xFF,  # PUSH1 0xFF
            0x60, 0x00,  # PUSH1 0 (offset)
            0x52,        # MSTORE
            0x60, 0x00,  # PUSH1 0 (offset)
            0x51,        # MLOAD
            0x50,        # POP (discard)
            0x00,        # STOP
        ])

        iterations = 1000
        times: List[float] = []

        for _ in range(iterations):
            start = time.perf_counter()
            result = qvm.execute(
                caller="0x" + "a" * 40,
                address="0x" + "b" * 40,
                code=code,
                gas=100_000,
            )
            elapsed = time.perf_counter() - start
            times.append(elapsed)
            assert result.success, f"Execution failed: {result.revert_reason}"

        avg_us = statistics.mean(times) * 1_000_000
        print(f"\nMemory operations: {avg_us:.1f} us/call ({iterations} iterations)")
        assert avg_us < 10_000, f"Memory operations too slow: {avg_us:.1f}us"

    def test_keccak256_opcode(self) -> None:
        """Benchmark: SHA3 (keccak256) opcode execution."""
        qvm = self._make_qvm()

        # Store 32 bytes at memory[0], then SHA3 it
        code = bytes([
            0x60, 0x42,  # PUSH1 0x42
            0x60, 0x00,  # PUSH1 0
            0x52,        # MSTORE (store 0x42 at offset 0)
            0x60, 0x20,  # PUSH1 32 (size)
            0x60, 0x00,  # PUSH1 0 (offset)
            0x20,        # SHA3 (keccak256)
            0x50,        # POP
            0x00,        # STOP
        ])

        iterations = 500
        times: List[float] = []

        for _ in range(iterations):
            start = time.perf_counter()
            result = qvm.execute(
                caller="0x" + "a" * 40,
                address="0x" + "b" * 40,
                code=code,
                gas=100_000,
            )
            elapsed = time.perf_counter() - start
            times.append(elapsed)
            assert result.success, f"Execution failed: {result.revert_reason}"

        avg_us = statistics.mean(times) * 1_000_000
        print(f"\nKeccak256 opcode: {avg_us:.1f} us/call ({iterations} iterations)")
        assert avg_us < 10_000, f"Keccak256 opcode too slow: {avg_us:.1f}us"


# ─── Reward Calculation Benchmark ───────────────────────────────────────────

class TestRewardCalculationBenchmark:
    """Benchmark the phi-halving reward calculation."""

    def test_reward_calculation_speed(self) -> None:
        """Benchmark: calculate_reward for various heights and eras."""
        import logging
        from qubitcoin.consensus.engine import ConsensusEngine
        qe = MagicMock()
        db = MagicMock()
        p2p = MagicMock()
        engine = ConsensusEngine(qe, db, p2p)

        iterations = 10000
        times: List[float] = []

        # Suppress debug logging during measurement — logger.debug() is part
        # of production code but adds ~1us overhead per call via I/O formatting
        consensus_logger = logging.getLogger("qubitcoin.consensus.engine")
        original_level = consensus_logger.level
        consensus_logger.setLevel(logging.WARNING)

        try:
            for i in range(iterations):
                height = i * 1000  # Span multiple eras
                start = time.perf_counter()
                _ = engine.calculate_reward(height, Decimal("1000000"))
                elapsed = time.perf_counter() - start
                times.append(elapsed)
        finally:
            consensus_logger.setLevel(original_level)

        avg_us = statistics.mean(times) * 1_000_000
        print(f"\nReward calculation: {avg_us:.2f} us/call ({iterations} iterations)")
        assert avg_us < 1000, f"Reward calculation too slow: {avg_us:.2f}us"


# ─── Combined Summary ──────────────────────────────────────────────────────

class TestBenchmarkSummary:
    """Run a combined benchmark and print a summary table."""

    def test_print_summary(self) -> None:
        """Print a summary of all micro-benchmarks (non-VQE)."""
        import logging
        from qubitcoin.consensus.engine import ConsensusEngine
        from qubitcoin.database.models import Block, Transaction, UTXO

        # Suppress debug logging during benchmark measurements
        consensus_logger = logging.getLogger("qubitcoin.consensus.engine")
        original_level = consensus_logger.level
        consensus_logger.setLevel(logging.WARNING)

        results: List[Tuple[str, str, str, str]] = []

        # ── Block hash ─────────────────────────────────────────────
        n = 1000
        prev_hash = "0" * 64
        blocks = []
        for i in range(n):
            coinbase = Transaction(
                txid=hashlib.sha256(f"cb{i}".encode()).hexdigest(),
                inputs=[],
                outputs=[{"address": "qbc1miner", "amount": Decimal("15.27")}],
                fee=Decimal(0),
                signature="",
                public_key="",
                timestamp=time.time(),
            )
            b = Block(
                height=i, prev_hash=prev_hash,
                proof_data={"params": [0.1], "energy": 0.5, "challenge": []},
                transactions=[coinbase], timestamp=time.time(), difficulty=1.0,
            )
            blocks.append(b)

        start = time.perf_counter()
        for b in blocks:
            b.calculate_hash()
        elapsed = time.perf_counter() - start
        avg_us = (elapsed / n) * 1_000_000
        results.append(("Block hash", str(n), f"{avg_us:.1f}", "us"))

        # ── UTXO serialization ─────────────────────────────────────
        utxo = UTXO(
            txid="a" * 64, vout=0, amount=Decimal("15.27"),
            address="qbc1test", proof={"e": 0.5}, block_height=100,
        )
        n = 10000
        start = time.perf_counter()
        for _ in range(n):
            d = utxo.to_dict()
            UTXO.from_dict(d)
        elapsed = time.perf_counter() - start
        avg_us = (elapsed / n) * 1_000_000
        results.append(("UTXO round-trip", str(n), f"{avg_us:.1f}", "us"))

        # ── Transaction serialization ──────────────────────────────
        tx = Transaction(
            txid="b" * 64,
            inputs=[{"txid": "a" * 64, "vout": 0}],
            outputs=[{"address": "qbc1recv", "amount": Decimal("10")}],
            fee=Decimal("0.0001"), signature="s" * 20,
            public_key="p" * 20, timestamp=time.time(),
        )
        n = 10000
        start = time.perf_counter()
        for _ in range(n):
            d = tx.to_dict()
            Transaction.from_dict(d)
        elapsed = time.perf_counter() - start
        avg_us = (elapsed / n) * 1_000_000
        results.append(("Tx round-trip", str(n), f"{avg_us:.1f}", "us"))

        # ── Reward calculation ─────────────────────────────────────
        qe = MagicMock()
        db = MagicMock()
        p2p = MagicMock()
        engine = ConsensusEngine(qe, db, p2p)
        n = 10000
        start = time.perf_counter()
        for i in range(n):
            engine.calculate_reward(i * 1000, Decimal("1000000"))
        elapsed = time.perf_counter() - start
        avg_us = (elapsed / n) * 1_000_000
        results.append(("Reward calc", str(n), f"{avg_us:.1f}", "us"))

        # ── QVM arithmetic ─────────────────────────────────────────
        from qubitcoin.qvm.vm import QVM
        mock_db = _make_mock_db()
        qvm = QVM(mock_db, quantum_engine=None, compliance_engine=None)
        code = bytes([0x60, 0x0a, 0x60, 0x14, 0x01, 0x60, 0x03, 0x02, 0x00])
        n = 1000
        start = time.perf_counter()
        for _ in range(n):
            qvm.execute(
                caller="0x" + "a" * 40, address="0x" + "b" * 40,
                code=code, gas=100_000,
            )
        elapsed = time.perf_counter() - start
        avg_us = (elapsed / n) * 1_000_000
        results.append(("QVM arithmetic", str(n), f"{avg_us:.1f}", "us"))

        # Restore logging
        consensus_logger.setLevel(original_level)

        print("\n" + "=" * 70)
        print("QUBITCOIN CORE PERFORMANCE BENCHMARKS")
        print("=" * 70)
        print(_format_table(results))
        print("=" * 70)
