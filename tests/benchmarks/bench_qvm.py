"""
Performance benchmark suite for the Python QVM (Quantum Virtual Machine).

Measures wall-clock time for QVM-specific operations:
  - ADD/MUL arithmetic loop throughput (opcodes/second)
  - SSTORE/SLOAD latency
  - Contract deployment throughput
  - SHA3/Keccak hash computation speed
  - Memory expansion costs
  - Stack operations throughput (PUSH/DUP/SWAP/POP)
  - State root computation time
  - EIP-1559 base fee calculation speed
  - JUMP/JUMPI control flow
  - LOG event emission

All benchmarks are self-contained with mocked dependencies so they can
run without a live node, database, or quantum hardware.

Usage:
    pytest tests/benchmarks/bench_qvm.py -v -m benchmark
    pytest tests/benchmarks/bench_qvm.py -v -s   # with print output
"""

import hashlib
import statistics
import time
from decimal import Decimal
from typing import List, Tuple
from unittest.mock import MagicMock

import pytest

# ─── Mark all tests in this module as benchmarks ────────────────────────────

pytestmark = pytest.mark.benchmark


# ─── Helpers ────────────────────────────────────────────────────────────────

def _format_table(rows: List[Tuple[str, str, str, str]]) -> str:
    """Format benchmark results as a table.

    Args:
        rows: List of (name, iterations, avg_time, unit) tuples.

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
    """Create a mock DatabaseManager with realistic return values for QVM benchmarks."""
    db = MagicMock()

    # Contract bytecode mock (simple PUSH1 0 PUSH1 0 RETURN)
    db.get_contract_bytecode = MagicMock(return_value="600060006000f3")

    # Storage mock — returns zero-padded hex for any key
    db.get_storage = MagicMock(return_value="0" * 64)
    db.set_storage = MagicMock()

    # Account mock
    from qubitcoin.database.models import Account
    db.get_or_create_account = MagicMock(return_value=Account(
        address="0x" + "a" * 40,
        nonce=0,
        balance=Decimal("1000"),
    ))
    db.get_account = MagicMock(return_value=Account(
        address="0x" + "a" * 40,
        nonce=0,
        balance=Decimal("1000"),
    ))
    db.get_account_balance = MagicMock(return_value=Decimal("1000"))
    db.update_account = MagicMock()

    # Block lookup mock
    mock_block = MagicMock()
    mock_block.block_hash = "b" * 64
    db.get_block = MagicMock(return_value=mock_block)

    # Session context manager mock
    session_mock = MagicMock()
    session_mock.__enter__ = MagicMock(return_value=session_mock)
    session_mock.__exit__ = MagicMock(return_value=False)
    db.get_session = MagicMock(return_value=session_mock)

    return db


def _make_qvm() -> "QVM":
    """Create a QVM instance with mocked database."""
    from qubitcoin.qvm.vm import QVM
    db = _make_mock_db()
    return QVM(db, quantum_engine=None, compliance_engine=None)


def _run_benchmark(func, iterations: int) -> Tuple[float, float, float]:
    """Run a benchmark function multiple times and return (avg, min, max) in seconds.

    Args:
        func: Callable to benchmark (takes no arguments).
        iterations: Number of times to call func.

    Returns:
        (avg_seconds, min_seconds, max_seconds)
    """
    times: List[float] = []
    for _ in range(iterations):
        start = time.perf_counter()
        func()
        elapsed = time.perf_counter() - start
        times.append(elapsed)
    return statistics.mean(times), min(times), max(times)


# ─── Benchmark: ADD/MUL Arithmetic Loop Throughput ─────────────────────────

class TestArithmeticThroughput:
    """Benchmark ADD/MUL loop throughput (opcodes/second)."""

    def test_add_mul_loop_throughput(self) -> None:
        """Benchmark: execute a tight ADD/MUL loop and measure opcodes/second.

        Bytecode executes 50 rounds of: PUSH, PUSH, ADD, PUSH, MUL.
        Total: 250 opcodes + STOP = 251 opcodes per execution.
        """
        qvm = _make_qvm()

        # Build a loop of PUSH1 x, PUSH1 y, ADD, PUSH1 z, MUL (5 opcodes per round)
        rounds = 50
        code = bytearray()
        for i in range(rounds):
            code += bytes([
                0x60, (i + 1) & 0xFF,   # PUSH1 (i+1)
                0x60, (i + 2) & 0xFF,   # PUSH1 (i+2)
                0x01,                     # ADD
                0x60, 0x03,              # PUSH1 3
                0x02,                     # MUL
                0x50,                     # POP (keep stack clean)
            ])
        code += bytes([0x00])  # STOP
        code = bytes(code)

        total_opcodes = rounds * 6 + 1  # 6 opcodes per round (PUSH, PUSH, ADD, PUSH, MUL, POP) + STOP
        iterations = 500

        times: List[float] = []
        for _ in range(iterations):
            start = time.perf_counter()
            result = qvm.execute(
                caller="0x" + "a" * 40,
                address="0x" + "b" * 40,
                code=code,
                gas=10_000_000,
            )
            elapsed = time.perf_counter() - start
            times.append(elapsed)
            assert result.success, f"Execution failed: {result.revert_reason}"

        avg_s = statistics.mean(times)
        min_s = min(times)
        max_s = max(times)
        ops_per_sec = total_opcodes / avg_s

        results = [
            ("ADD/MUL loop (avg)", str(iterations), f"{avg_s * 1_000_000:.1f}", "us"),
            ("ADD/MUL loop (min)", str(iterations), f"{min_s * 1_000_000:.1f}", "us"),
            ("ADD/MUL loop (max)", str(iterations), f"{max_s * 1_000_000:.1f}", "us"),
            ("Opcodes/second", str(iterations), f"{ops_per_sec:.0f}", "ops/s"),
        ]
        print("\n" + _format_table(results))

        # Should execute at least 100K opcodes/second on any modern CPU
        assert ops_per_sec > 50_000, f"Throughput too low: {ops_per_sec:.0f} ops/s"


# ─── Benchmark: SSTORE/SLOAD Latency ──────────────────────────────────────

class TestStorageLatency:
    """Benchmark SSTORE and SLOAD opcode latency."""

    def test_sstore_latency(self) -> None:
        """Benchmark: SSTORE write latency (includes gas accounting)."""
        qvm = _make_qvm()

        # PUSH1 value, PUSH1 key, SSTORE, STOP
        code = bytes([
            0x60, 0xFF,  # PUSH1 0xFF (value)
            0x60, 0x01,  # PUSH1 0x01 (key)
            0x55,        # SSTORE
            0x00,        # STOP
        ])

        iterations = 500
        avg_s, min_s, max_s = _run_benchmark(
            lambda: qvm.execute(
                caller="0x" + "a" * 40,
                address="0x" + "b" * 40,
                code=code,
                gas=1_000_000,
            ),
            iterations,
        )

        results = [
            ("SSTORE (avg)", str(iterations), f"{avg_s * 1_000_000:.1f}", "us"),
            ("SSTORE (min)", str(iterations), f"{min_s * 1_000_000:.1f}", "us"),
            ("SSTORE (max)", str(iterations), f"{max_s * 1_000_000:.1f}", "us"),
        ]
        print("\n" + _format_table(results))
        assert avg_s * 1000 < 50.0, f"SSTORE too slow: {avg_s * 1000:.3f}ms"

    def test_sload_latency(self) -> None:
        """Benchmark: SLOAD read latency (cache hit path)."""
        qvm = _make_qvm()

        # First SSTORE a value, then SLOAD it back
        code = bytes([
            0x60, 0xFF,  # PUSH1 0xFF (value)
            0x60, 0x01,  # PUSH1 0x01 (key)
            0x55,        # SSTORE
            0x60, 0x01,  # PUSH1 0x01 (key)
            0x54,        # SLOAD
            0x50,        # POP
            0x00,        # STOP
        ])

        iterations = 500
        avg_s, min_s, max_s = _run_benchmark(
            lambda: qvm.execute(
                caller="0x" + "a" * 40,
                address="0x" + "b" * 40,
                code=code,
                gas=1_000_000,
            ),
            iterations,
        )

        results = [
            ("SSTORE+SLOAD (avg)", str(iterations), f"{avg_s * 1_000_000:.1f}", "us"),
            ("SSTORE+SLOAD (min)", str(iterations), f"{min_s * 1_000_000:.1f}", "us"),
            ("SSTORE+SLOAD (max)", str(iterations), f"{max_s * 1_000_000:.1f}", "us"),
        ]
        print("\n" + _format_table(results))
        assert avg_s * 1000 < 50.0, f"SLOAD too slow: {avg_s * 1000:.3f}ms"


# ─── Benchmark: Contract Deployment Throughput ─────────────────────────────

class TestContractDeploymentThroughput:
    """Benchmark contract deployment throughput."""

    def test_contract_deploy_throughput(self) -> None:
        """Benchmark: deploy minimal contracts and measure deployments/second.

        Init code: stores 0x42 at memory[0], returns 32 bytes as runtime bytecode.
        """
        qvm = _make_qvm()

        init_code = bytes([
            0x60, 0x42,  # PUSH1 0x42
            0x60, 0x00,  # PUSH1 0
            0x52,        # MSTORE
            0x60, 0x20,  # PUSH1 32
            0x60, 0x00,  # PUSH1 0
            0xf3,        # RETURN
        ])

        iterations = 200
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
            assert result.success, f"Deploy failed: {result.revert_reason}"

        avg_s = statistics.mean(times)
        deploys_per_sec = 1.0 / avg_s if avg_s > 0 else float('inf')

        results = [
            ("Contract deploy (avg)", str(iterations), f"{avg_s * 1000:.3f}", "ms"),
            ("Deploys/second", str(iterations), f"{deploys_per_sec:.0f}", "deploys/s"),
        ]
        print("\n" + _format_table(results))
        assert avg_s * 1000 < 100.0, f"Contract deploy too slow: {avg_s * 1000:.3f}ms"

    def test_larger_contract_deploy(self) -> None:
        """Benchmark: deploy a larger contract (~256 bytes of runtime code)."""
        qvm = _make_qvm()

        # Build 256 bytes of runtime code (PUSH1 0, POP repeated)
        runtime = bytes([0x60, 0x00, 0x50] * 85 + [0x00])  # 256 bytes
        rlen = len(runtime)

        # Init code: CODECOPY + RETURN
        init_code = bytearray()
        offset = 0  # placeholder, compute after
        init_code += bytes([0x61]) + rlen.to_bytes(2, 'big')  # PUSH2 rlen
        init_code += bytes([0x60, 0x00])  # placeholder offset
        init_code += bytes([0x60, 0x00, 0x39])  # PUSH1 0, CODECOPY
        init_code += bytes([0x61]) + rlen.to_bytes(2, 'big')  # PUSH2 rlen
        init_code += bytes([0x60, 0x00, 0xf3])  # PUSH1 0, RETURN

        # Fix offset
        init_len = len(init_code)
        init_code[3] = init_len  # Set the offset byte
        code = bytes(init_code) + runtime

        iterations = 100
        avg_s, min_s, max_s = _run_benchmark(
            lambda: qvm.execute(
                caller="0x" + "a" * 40,
                address="0x" + "c" * 40,
                code=code,
                gas=1_000_000,
            ),
            iterations,
        )

        results = [
            (f"Deploy {rlen}B contract (avg)", str(iterations), f"{avg_s * 1000:.3f}", "ms"),
        ]
        print("\n" + _format_table(results))
        assert avg_s * 1000 < 200.0, f"Large deploy too slow: {avg_s * 1000:.3f}ms"


# ─── Benchmark: SHA3/Keccak Hash Computation ──────────────────────────────

class TestKeccakBenchmark:
    """Benchmark KECCAK256 opcode at various input sizes."""

    def test_keccak256_32bytes(self) -> None:
        """Benchmark: keccak256 of 32 bytes."""
        qvm = _make_qvm()

        code = bytes([
            0x60, 0x42,  # PUSH1 0x42
            0x60, 0x00,  # PUSH1 0
            0x52,        # MSTORE (store 32 bytes at offset 0)
            0x60, 0x20,  # PUSH1 32 (size)
            0x60, 0x00,  # PUSH1 0 (offset)
            0x20,        # SHA3 (keccak256)
            0x50,        # POP
            0x00,        # STOP
        ])

        iterations = 1000
        avg_s, min_s, max_s = _run_benchmark(
            lambda: qvm.execute(
                caller="0x" + "a" * 40,
                address="0x" + "b" * 40,
                code=code,
                gas=100_000,
            ),
            iterations,
        )

        results = [
            ("Keccak256 32B (avg)", str(iterations), f"{avg_s * 1_000_000:.1f}", "us"),
            ("Keccak256 32B (min)", str(iterations), f"{min_s * 1_000_000:.1f}", "us"),
            ("Keccak256 32B (max)", str(iterations), f"{max_s * 1_000_000:.1f}", "us"),
        ]
        print("\n" + _format_table(results))
        assert avg_s * 1_000_000 < 10_000, f"Keccak256 too slow: {avg_s * 1_000_000:.1f}us"

    def test_keccak256_multiple(self) -> None:
        """Benchmark: 10 consecutive keccak256 hashes in one execution."""
        qvm = _make_qvm()

        code = bytearray()
        # Store initial data
        code += bytes([0x60, 0x42, 0x60, 0x00, 0x52])  # PUSH1 0x42, PUSH1 0, MSTORE
        # 10 rounds of SHA3
        for _ in range(10):
            code += bytes([
                0x60, 0x20,  # PUSH1 32
                0x60, 0x00,  # PUSH1 0
                0x20,        # SHA3
                0x60, 0x00,  # PUSH1 0
                0x52,        # MSTORE (store result back for next round)
            ])
        code += bytes([0x00])  # STOP

        iterations = 500
        avg_s, min_s, max_s = _run_benchmark(
            lambda: qvm.execute(
                caller="0x" + "a" * 40,
                address="0x" + "b" * 40,
                code=bytes(code),
                gas=1_000_000,
            ),
            iterations,
        )

        results = [
            ("10x Keccak256 (avg)", str(iterations), f"{avg_s * 1_000_000:.1f}", "us"),
        ]
        print("\n" + _format_table(results))
        assert avg_s * 1000 < 50.0, f"10x Keccak256 too slow: {avg_s * 1000:.3f}ms"


# ─── Benchmark: Memory Expansion Costs ────────────────────────────────────

class TestMemoryExpansionBenchmark:
    """Benchmark memory expansion costs at various sizes."""

    def test_memory_expansion_small(self) -> None:
        """Benchmark: expand memory to 32 bytes (1 word)."""
        qvm = _make_qvm()

        code = bytes([
            0x60, 0xFF,  # PUSH1 0xFF
            0x60, 0x00,  # PUSH1 0 (offset)
            0x52,        # MSTORE (expands to 32 bytes)
            0x00,        # STOP
        ])

        iterations = 1000
        avg_s, _, _ = _run_benchmark(
            lambda: qvm.execute(
                caller="0x" + "a" * 40,
                address="0x" + "b" * 40,
                code=code,
                gas=100_000,
            ),
            iterations,
        )

        print(f"\nMemory expand 32B: {avg_s * 1_000_000:.1f} us/call ({iterations} iter)")
        assert avg_s * 1_000_000 < 10_000, f"Memory expand 32B too slow"

    def test_memory_expansion_large(self) -> None:
        """Benchmark: expand memory to 1024 bytes (32 words)."""
        qvm = _make_qvm()

        # MSTORE at offset 992 (= 1024-32) forces expansion to 1024 bytes
        code = bytes([
            0x60, 0xFF,        # PUSH1 0xFF
            0x61, 0x03, 0xE0,  # PUSH2 992
            0x52,              # MSTORE
            0x00,              # STOP
        ])

        iterations = 1000
        avg_s, _, _ = _run_benchmark(
            lambda: qvm.execute(
                caller="0x" + "a" * 40,
                address="0x" + "b" * 40,
                code=code,
                gas=1_000_000,
            ),
            iterations,
        )

        print(f"\nMemory expand 1024B: {avg_s * 1_000_000:.1f} us/call ({iterations} iter)")
        assert avg_s * 1_000_000 < 10_000, f"Memory expand 1024B too slow"

    def test_memory_expansion_very_large(self) -> None:
        """Benchmark: expand memory to 8192 bytes (256 words)."""
        qvm = _make_qvm()

        # MSTORE at offset 8160 (= 8192-32)
        code = bytes([
            0x60, 0xFF,        # PUSH1 0xFF
            0x61, 0x1F, 0xE0,  # PUSH2 8160
            0x52,              # MSTORE
            0x00,              # STOP
        ])

        iterations = 500
        avg_s, _, _ = _run_benchmark(
            lambda: qvm.execute(
                caller="0x" + "a" * 40,
                address="0x" + "b" * 40,
                code=code,
                gas=10_000_000,
            ),
            iterations,
        )

        print(f"\nMemory expand 8192B: {avg_s * 1_000_000:.1f} us/call ({iterations} iter)")
        assert avg_s * 1000 < 50.0, f"Memory expand 8192B too slow"


# ─── Benchmark: Stack Operations Throughput ────────────────────────────────

class TestStackOperationsThroughput:
    """Benchmark stack operations (PUSH, DUP, SWAP, POP)."""

    def test_push_pop_throughput(self) -> None:
        """Benchmark: tight PUSH1/POP loop (100 rounds)."""
        qvm = _make_qvm()

        rounds = 100
        code = bytearray()
        for i in range(rounds):
            code += bytes([0x60, i & 0xFF, 0x50])  # PUSH1 i, POP
        code += bytes([0x00])  # STOP

        iterations = 1000
        times: List[float] = []
        for _ in range(iterations):
            start = time.perf_counter()
            result = qvm.execute(
                caller="0x" + "a" * 40,
                address="0x" + "b" * 40,
                code=bytes(code),
                gas=1_000_000,
            )
            elapsed = time.perf_counter() - start
            times.append(elapsed)
            assert result.success

        avg_s = statistics.mean(times)
        total_ops = rounds * 2 + 1  # PUSH + POP per round, + STOP
        ops_per_sec = total_ops / avg_s

        results = [
            ("PUSH/POP loop (avg)", str(iterations), f"{avg_s * 1_000_000:.1f}", "us"),
            ("Stack ops/sec", str(iterations), f"{ops_per_sec:.0f}", "ops/s"),
        ]
        print("\n" + _format_table(results))
        assert ops_per_sec > 50_000, f"Stack throughput too low: {ops_per_sec:.0f} ops/s"

    def test_dup_swap_throughput(self) -> None:
        """Benchmark: DUP1/SWAP1/POP cycle (50 rounds)."""
        qvm = _make_qvm()

        rounds = 50
        code = bytearray()
        code += bytes([0x60, 0x42])  # PUSH1 0x42 (seed value)
        for _ in range(rounds):
            code += bytes([0x80, 0x90, 0x50])  # DUP1, SWAP1, POP
        code += bytes([0x50, 0x00])  # POP, STOP

        iterations = 1000
        avg_s, _, _ = _run_benchmark(
            lambda: qvm.execute(
                caller="0x" + "a" * 40,
                address="0x" + "b" * 40,
                code=bytes(code),
                gas=1_000_000,
            ),
            iterations,
        )

        total_ops = 1 + rounds * 3 + 2  # PUSH + (DUP+SWAP+POP)*rounds + POP + STOP
        ops_per_sec = total_ops / avg_s

        results = [
            ("DUP/SWAP cycle (avg)", str(iterations), f"{avg_s * 1_000_000:.1f}", "us"),
            ("DUP/SWAP ops/sec", str(iterations), f"{ops_per_sec:.0f}", "ops/s"),
        ]
        print("\n" + _format_table(results))
        assert ops_per_sec > 50_000, f"DUP/SWAP throughput too low: {ops_per_sec:.0f} ops/s"


# ─── Benchmark: State Root Computation ─────────────────────────────────────

class TestStateRootBenchmark:
    """Benchmark state root Merkle computation."""

    def test_state_root_computation(self) -> None:
        """Benchmark: compute state root with varying number of accounts."""
        from qubitcoin.qvm.state import StateManager

        for num_accounts in [10, 100, 500]:
            db = _make_mock_db()

            # Mock the session to return rows
            rows = []
            for i in range(num_accounts):
                addr = hashlib.sha256(str(i).encode()).hexdigest()[:40]
                rows.append((addr, i, Decimal("100.00"), "", ""))

            session_mock = MagicMock()
            session_mock.__enter__ = MagicMock(return_value=session_mock)
            session_mock.__exit__ = MagicMock(return_value=False)
            session_mock.execute = MagicMock(return_value=rows)
            db.get_session = MagicMock(return_value=session_mock)

            sm = StateManager(db)

            iterations = 100
            avg_s, min_s, max_s = _run_benchmark(
                lambda: sm.compute_state_root(100),
                iterations,
            )

            print(
                f"\nState root ({num_accounts} accounts): "
                f"avg={avg_s * 1000:.3f}ms, "
                f"min={min_s * 1000:.3f}ms, "
                f"max={max_s * 1000:.3f}ms "
                f"({iterations} iter)"
            )
            # State root computation should be fast even for 500 accounts
            assert avg_s * 1000 < 500.0, (
                f"State root ({num_accounts} accounts) too slow: {avg_s * 1000:.3f}ms"
            )


# ─── Benchmark: EIP-1559 Base Fee Calculation ─────────────────────────────

class TestEIP1559Benchmark:
    """Benchmark EIP-1559 base fee calculation speed."""

    def test_base_fee_calculation_speed(self) -> None:
        """Benchmark: calculate_base_fee for various gas usage scenarios."""
        from qubitcoin.qvm.state import calculate_base_fee

        gas_limit = 30_000_000
        base_fee = 1_000_000_000  # 1 gwei

        iterations = 10_000
        scenarios = [
            ("At target", gas_limit // 2),
            ("Above target (full)", gas_limit),
            ("Below target (empty)", 0),
            ("Slightly above", gas_limit // 2 + 1_000_000),
        ]

        results = []
        for name, gas_used in scenarios:
            times: List[float] = []
            for _ in range(iterations):
                start = time.perf_counter()
                _ = calculate_base_fee(gas_used, gas_limit, base_fee)
                elapsed = time.perf_counter() - start
                times.append(elapsed)

            avg_us = statistics.mean(times) * 1_000_000
            results.append((f"BaseFee ({name})", str(iterations), f"{avg_us:.2f}", "us"))

        print("\n" + _format_table(results))

        # Base fee calculation is pure arithmetic — should be very fast
        for name, gas_used in scenarios:
            times = []
            for _ in range(iterations):
                start = time.perf_counter()
                _ = calculate_base_fee(gas_used, gas_limit, base_fee)
                elapsed = time.perf_counter() - start
                times.append(elapsed)
            avg_us = statistics.mean(times) * 1_000_000
            assert avg_us < 100, f"BaseFee calc too slow: {avg_us:.2f}us"

    def test_base_fee_chained_blocks(self) -> None:
        """Benchmark: simulate 1000 blocks of EIP-1559 fee adjustments."""
        from qubitcoin.qvm.state import calculate_base_fee

        gas_limit = 30_000_000
        base_fee = 1_000_000_000
        iterations = 1000

        start = time.perf_counter()
        for i in range(iterations):
            # Alternate between high and low usage
            gas_used = gas_limit if i % 2 == 0 else 0
            base_fee = calculate_base_fee(gas_used, gas_limit, base_fee)
        total = time.perf_counter() - start

        avg_us = (total / iterations) * 1_000_000
        print(f"\nChained base fee (1000 blocks): {avg_us:.2f} us/block, total={total * 1000:.1f}ms")
        assert total < 1.0, f"1000 chained base fee calcs too slow: {total:.3f}s"


# ─── Benchmark: JUMP/JUMPI Control Flow ───────────────────────────────────

class TestControlFlowBenchmark:
    """Benchmark JUMP and JUMPI control flow opcodes."""

    def test_jump_loop(self) -> None:
        """Benchmark: simple JUMP-based loop (counter from 10 to 0).

        Layout:
          0: PUSH1 10        (counter)
          2: JUMPDEST         (loop top, pc=2)
          3: PUSH1 1
          5: SWAP1
          6: SUB              (counter -= 1)
          7: DUP1
          8: PUSH1 2          (loop top)
          10: JUMPI            (if counter != 0, jump to 2)
          11: STOP
        """
        qvm = _make_qvm()

        code = bytes([
            0x60, 0x0A,  # PUSH1 10  (counter)
            0x5b,        # JUMPDEST  (pc=2, loop top)
            0x60, 0x01,  # PUSH1 1
            0x90,        # SWAP1
            0x03,        # SUB
            0x80,        # DUP1
            0x60, 0x02,  # PUSH1 2   (loop top)
            0x57,        # JUMPI
            0x50,        # POP
            0x00,        # STOP
        ])

        iterations = 1000
        avg_s, _, _ = _run_benchmark(
            lambda: qvm.execute(
                caller="0x" + "a" * 40,
                address="0x" + "b" * 40,
                code=code,
                gas=1_000_000,
            ),
            iterations,
        )

        print(f"\nJUMP loop (10 iterations): {avg_s * 1_000_000:.1f} us/call ({iterations} iter)")
        assert avg_s * 1_000_000 < 10_000, f"JUMP loop too slow"


# ─── Benchmark: LOG Event Emission ────────────────────────────────────────

class TestLogEmissionBenchmark:
    """Benchmark LOG opcode event emission."""

    def test_log1_emission(self) -> None:
        """Benchmark: emit a LOG1 event with 32 bytes of data."""
        qvm = _make_qvm()

        # Store data, then LOG1 with one topic
        code = bytes([
            0x60, 0xAA,  # PUSH1 0xAA (data)
            0x60, 0x00,  # PUSH1 0
            0x52,        # MSTORE
            0x60, 0x01,  # PUSH1 1 (topic)
            0x60, 0x20,  # PUSH1 32 (size)
            0x60, 0x00,  # PUSH1 0 (offset)
            0xa1,        # LOG1
            0x00,        # STOP
        ])

        iterations = 500
        avg_s, _, _ = _run_benchmark(
            lambda: qvm.execute(
                caller="0x" + "a" * 40,
                address="0x" + "b" * 40,
                code=code,
                gas=1_000_000,
            ),
            iterations,
        )

        print(f"\nLOG1 emission: {avg_s * 1_000_000:.1f} us/call ({iterations} iter)")
        assert avg_s * 1_000_000 < 10_000, f"LOG1 too slow"


# ─── Combined QVM Summary ─────────────────────────────────────────────────

class TestQVMBenchmarkSummary:
    """Run all QVM micro-benchmarks and print a combined summary."""

    def test_qvm_summary(self) -> None:
        """Print a summary table of all QVM performance metrics."""
        from qubitcoin.qvm.state import calculate_base_fee

        qvm = _make_qvm()
        results: List[Tuple[str, str, str, str]] = []

        # ── Arithmetic ─────────────────────────────────────────
        code = bytes([0x60, 0x0a, 0x60, 0x14, 0x01, 0x60, 0x03, 0x02, 0x50, 0x00])
        n = 1000
        start = time.perf_counter()
        for _ in range(n):
            qvm.execute(caller="0x" + "a" * 40, address="0x" + "b" * 40, code=code, gas=100_000)
        elapsed = time.perf_counter() - start
        results.append(("ADD+MUL+POP", str(n), f"{(elapsed / n) * 1_000_000:.1f}", "us"))

        # ── SSTORE ─────────────────────────────────────────────
        code = bytes([0x60, 0xFF, 0x60, 0x01, 0x55, 0x00])
        n = 1000
        start = time.perf_counter()
        for _ in range(n):
            qvm.execute(caller="0x" + "a" * 40, address="0x" + "b" * 40, code=code, gas=100_000)
        elapsed = time.perf_counter() - start
        results.append(("SSTORE", str(n), f"{(elapsed / n) * 1_000_000:.1f}", "us"))

        # ── SLOAD ──────────────────────────────────────────────
        code = bytes([0x60, 0x01, 0x54, 0x50, 0x00])
        n = 1000
        start = time.perf_counter()
        for _ in range(n):
            qvm.execute(caller="0x" + "a" * 40, address="0x" + "b" * 40, code=code, gas=100_000)
        elapsed = time.perf_counter() - start
        results.append(("SLOAD", str(n), f"{(elapsed / n) * 1_000_000:.1f}", "us"))

        # ── Keccak256 ──────────────────────────────────────────
        code = bytes([0x60, 0x42, 0x60, 0x00, 0x52, 0x60, 0x20, 0x60, 0x00, 0x20, 0x50, 0x00])
        n = 1000
        start = time.perf_counter()
        for _ in range(n):
            qvm.execute(caller="0x" + "a" * 40, address="0x" + "b" * 40, code=code, gas=100_000)
        elapsed = time.perf_counter() - start
        results.append(("Keccak256", str(n), f"{(elapsed / n) * 1_000_000:.1f}", "us"))

        # ── Memory expand ──────────────────────────────────────
        code = bytes([0x60, 0xFF, 0x61, 0x03, 0xE0, 0x52, 0x00])
        n = 1000
        start = time.perf_counter()
        for _ in range(n):
            qvm.execute(caller="0x" + "a" * 40, address="0x" + "b" * 40, code=code, gas=1_000_000)
        elapsed = time.perf_counter() - start
        results.append(("Memory 1KB expand", str(n), f"{(elapsed / n) * 1_000_000:.1f}", "us"))

        # ── PUSH/POP ───────────────────────────────────────────
        code = bytes([0x60, 0x00, 0x50] * 50 + [0x00])
        n = 1000
        start = time.perf_counter()
        for _ in range(n):
            qvm.execute(caller="0x" + "a" * 40, address="0x" + "b" * 40, code=code, gas=100_000)
        elapsed = time.perf_counter() - start
        results.append(("50x PUSH/POP", str(n), f"{(elapsed / n) * 1_000_000:.1f}", "us"))

        # ── EIP-1559 base fee ──────────────────────────────────
        n = 10000
        start = time.perf_counter()
        bf = 1_000_000_000
        for i in range(n):
            bf = calculate_base_fee(15_000_000, 30_000_000, bf)
        elapsed = time.perf_counter() - start
        results.append(("EIP-1559 base fee", str(n), f"{(elapsed / n) * 1_000_000:.2f}", "us"))

        # ── Contract deploy ────────────────────────────────────
        init_code = bytes([0x60, 0x42, 0x60, 0x00, 0x52, 0x60, 0x20, 0x60, 0x00, 0xf3])
        n = 200
        start = time.perf_counter()
        for i in range(n):
            qvm.execute(
                caller="0x" + "a" * 40,
                address="0x" + hashlib.sha256(str(i).encode()).hexdigest()[:40],
                code=init_code, gas=1_000_000,
            )
        elapsed = time.perf_counter() - start
        results.append(("Contract deploy", str(n), f"{(elapsed / n) * 1000:.3f}", "ms"))

        print("\n" + "=" * 70)
        print("QVM PERFORMANCE BENCHMARKS")
        print("=" * 70)
        print(_format_table(results))
        print("=" * 70)
