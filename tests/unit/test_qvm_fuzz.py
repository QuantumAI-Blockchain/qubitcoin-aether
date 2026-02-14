"""QVM fuzz testing — random bytecode execution (Batch 11.3).

Generates random bytecode sequences and verifies the QVM never crashes,
always returning a structured ExecutionResult.
"""
import random
import pytest

from unittest.mock import MagicMock
from qubitcoin.qvm.vm import QVM, ExecutionResult
from qubitcoin.qvm.opcodes import Opcode


def _make_vm() -> QVM:
    return QVM(quantum_engine=MagicMock())


def _run(vm: QVM, bytecode: bytes, gas: int = 500_000) -> ExecutionResult:
    return vm.execute(
        '0x' + 'aa' * 20,
        '0x' + 'bb' * 20,
        bytecode,
        b'',
        0,
        gas,
    )


class TestFuzzRandomBytecode:
    """Execute purely random byte sequences — VM must never crash."""

    SEEDS = list(range(50))

    @pytest.mark.parametrize("seed", SEEDS)
    def test_random_bytes(self, seed: int):
        rng = random.Random(seed)
        length = rng.randint(1, 128)
        bytecode = bytes(rng.randint(0, 255) for _ in range(length))
        vm = _make_vm()
        result = _run(vm, bytecode)
        assert isinstance(result, ExecutionResult)
        assert isinstance(result.success, bool)
        assert isinstance(result.gas_used, int)
        assert result.gas_used >= 0


class TestFuzzValidOpcodeSequences:
    """Generate sequences that mix valid opcodes with random args."""

    SEEDS = list(range(30))

    @pytest.mark.parametrize("seed", SEEDS)
    def test_valid_opcode_mix(self, seed: int):
        rng = random.Random(seed)
        bytecode = bytearray()
        valid_ops = [
            Opcode.STOP, Opcode.ADD, Opcode.MUL, Opcode.SUB, Opcode.DIV,
            Opcode.MOD, Opcode.EXP, Opcode.LT, Opcode.GT, Opcode.EQ,
            Opcode.ISZERO, Opcode.AND, Opcode.OR, Opcode.XOR, Opcode.NOT,
            Opcode.POP, Opcode.MLOAD, Opcode.MSTORE,
            Opcode.PUSH1, Opcode.DUP1, Opcode.SWAP1,
        ]
        for _ in range(rng.randint(2, 40)):
            op = rng.choice(valid_ops)
            bytecode.append(op)
            # PUSH1 must be followed by a data byte
            if op == Opcode.PUSH1:
                bytecode.append(rng.randint(0, 255))
        vm = _make_vm()
        result = _run(vm, bytes(bytecode))
        assert isinstance(result, ExecutionResult)


class TestFuzzPushOverflow:
    """PUSH instructions near the end of bytecode (truncated operands)."""

    def test_push1_at_end(self):
        """PUSH1 with no data byte — must not crash."""
        vm = _make_vm()
        result = _run(vm, bytes([Opcode.PUSH1]))
        assert isinstance(result, ExecutionResult)

    def test_push32_truncated(self):
        """PUSH32 with fewer than 32 data bytes."""
        vm = _make_vm()
        bytecode = bytes([Opcode.PUSH32]) + b'\xff' * 10
        result = _run(vm, bytecode)
        assert isinstance(result, ExecutionResult)

    def test_all_pushN_truncated(self):
        """Each PUSH1..PUSH32 with zero data bytes."""
        vm = _make_vm()
        for n in range(1, 33):
            push_op = Opcode.PUSH1 + (n - 1)
            result = _run(vm, bytes([push_op]))
            assert isinstance(result, ExecutionResult), f"PUSH{n} crashed"


class TestFuzzStackStress:
    """Deep stack operations."""

    def test_deep_push_pop(self):
        """Push 200 values then pop them all."""
        vm = _make_vm()
        bc = bytearray()
        for _ in range(200):
            bc.extend([Opcode.PUSH1, 0x42])
        for _ in range(200):
            bc.append(Opcode.POP)
        bc.append(Opcode.STOP)
        result = _run(vm, bytes(bc), gas=2_000_000)
        assert result.success is True

    def test_stack_overflow(self):
        """Exceed 1024-item stack limit — should revert, not crash."""
        vm = _make_vm()
        bc = bytearray()
        for _ in range(1030):
            bc.extend([Opcode.PUSH1, 0x01])
        result = _run(vm, bytes(bc), gas=2_000_000)
        assert isinstance(result, ExecutionResult)
        # Stack overflow should cause revert
        assert result.success is False


class TestFuzzMemoryStress:
    """Large memory operations."""

    def test_large_mstore_offset(self):
        """MSTORE at a large offset — should not crash (may OOG)."""
        vm = _make_vm()
        bc = bytes([
            Opcode.PUSH1, 0xFF,        # value
            Opcode.PUSH2, 0x10, 0x00,  # offset = 4096
            Opcode.MSTORE,
            Opcode.STOP,
        ])
        result = _run(vm, bc)
        assert isinstance(result, ExecutionResult)

    def test_zero_length_return(self):
        """RETURN with zero length — should succeed with empty data."""
        vm = _make_vm()
        bc = bytes([
            Opcode.PUSH1, 0,  # length = 0
            Opcode.PUSH1, 0,  # offset = 0
            Opcode.RETURN,
        ])
        result = _run(vm, bc)
        assert result.success is True
        assert result.return_data == b''


class TestFuzzQuantumOpcodes:
    """Random quantum opcode invocations."""

    def test_qcreate_boundary_qubits(self):
        """QCREATE with qubit counts 0 and 255."""
        vm = _make_vm()
        for n in [0, 1, 255]:
            bc = bytes([Opcode.PUSH1, n, Opcode.QCREATE, Opcode.POP, Opcode.STOP])
            result = _run(vm, bc)
            assert isinstance(result, ExecutionResult)

    def test_qverify_random_inputs(self):
        """QVERIFY with random stack inputs."""
        vm = _make_vm()
        rng = random.Random(99)
        for _ in range(10):
            a = rng.randint(0, 255)
            b = rng.randint(0, 255)
            bc = bytes([Opcode.PUSH1, a, Opcode.PUSH1, b, Opcode.QVERIFY,
                        Opcode.POP, Opcode.STOP])
            result = _run(vm, bc)
            assert isinstance(result, ExecutionResult)
