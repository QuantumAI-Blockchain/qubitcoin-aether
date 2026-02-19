"""Fuzz tests — random bytecode to QVM, ensuring no crashes or panics.

These tests generate random bytecode sequences and feed them to the QVM.
The goal is NOT correct execution, but ensuring the QVM handles any input
gracefully without crashes, infinite loops, or uncaught exceptions.
"""
import pytest
import random
import struct
from unittest.mock import MagicMock


class TestRandomBytecode:
    """Feed random bytecode to QVM to check crash resistance."""

    def _make_qvm(self):
        from qubitcoin.qvm.vm import QVM
        return QVM(db_manager=None, quantum_engine=None)

    def test_empty_bytecode(self):
        """Empty bytecode completes without error."""
        qvm = self._make_qvm()
        result = qvm.execute(
            caller='0x' + 'a' * 40,
            address='0x' + 'b' * 40,
            code=b'',
            gas=100000,
        )
        assert result.success is True

    def test_single_stop(self):
        """Single STOP opcode executes cleanly."""
        from qubitcoin.qvm.opcodes import Opcode
        qvm = self._make_qvm()
        result = qvm.execute(
            caller='0x' + 'a' * 40,
            address='0x' + 'b' * 40,
            code=bytes([Opcode.STOP]),
            gas=100000,
        )
        assert result.success is True

    def test_random_bytes_100_runs(self):
        """100 random bytecode sequences do not crash the QVM."""
        qvm = self._make_qvm()
        rng = random.Random(42)  # deterministic seed for reproducibility
        for i in range(100):
            length = rng.randint(1, 256)
            code = bytes(rng.randint(0, 255) for _ in range(length))
            result = qvm.execute(
                caller='0x' + 'a' * 40,
                address='0x' + 'b' * 40,
                code=code,
                gas=100000,
            )
            # Should complete without raising; success or failure are both OK
            assert isinstance(result.success, bool), f"Run {i}: result.success is not bool"

    def test_all_single_byte_opcodes(self):
        """Every possible single-byte value (0x00-0xFF) is handled."""
        qvm = self._make_qvm()
        for opcode_val in range(256):
            code = bytes([opcode_val])
            result = qvm.execute(
                caller='0x' + 'a' * 40,
                address='0x' + 'b' * 40,
                code=code,
                gas=100000,
            )
            assert isinstance(result.success, bool), f"Opcode 0x{opcode_val:02x} crashed"

    def test_repeated_push_pop(self):
        """Repeated PUSH1/POP sequences don't crash."""
        from qubitcoin.qvm.opcodes import Opcode
        qvm = self._make_qvm()
        # 500 rounds of PUSH1 value, POP
        code = bytes([Opcode.PUSH1, 0x42, Opcode.POP] * 500 + [Opcode.STOP])
        result = qvm.execute(
            caller='0x' + 'a' * 40,
            address='0x' + 'b' * 40,
            code=code,
            gas=10_000_000,
        )
        assert result.success is True

    def test_stack_overflow_recovery(self):
        """Pushing more than 1024 items is handled gracefully."""
        from qubitcoin.qvm.opcodes import Opcode
        qvm = self._make_qvm()
        # Push 1100 items (exceeds 1024 stack limit)
        code = bytes([Opcode.PUSH1, 1] * 1100 + [Opcode.STOP])
        result = qvm.execute(
            caller='0x' + 'a' * 40,
            address='0x' + 'b' * 40,
            code=code,
            gas=10_000_000,
        )
        # Should fail gracefully (stack overflow), not crash
        assert isinstance(result.success, bool)

    def test_stack_underflow_recovery(self):
        """Popping from empty stack is handled gracefully."""
        from qubitcoin.qvm.opcodes import Opcode
        qvm = self._make_qvm()
        # POP with nothing on stack
        code = bytes([Opcode.POP, Opcode.STOP])
        result = qvm.execute(
            caller='0x' + 'a' * 40,
            address='0x' + 'b' * 40,
            code=code,
            gas=100000,
        )
        # Should fail gracefully, not crash
        assert isinstance(result.success, bool)

    def test_out_of_gas_recovery(self):
        """Execution with minimal gas runs out cleanly."""
        from qubitcoin.qvm.opcodes import Opcode
        qvm = self._make_qvm()
        # Long computation with very little gas
        code = bytes([Opcode.PUSH1, 1, Opcode.PUSH1, 2, Opcode.ADD] * 100)
        result = qvm.execute(
            caller='0x' + 'a' * 40,
            address='0x' + 'b' * 40,
            code=code,
            gas=10,  # very little gas
        )
        assert result.success is False  # should run out of gas

    def test_invalid_jump_recovery(self):
        """JUMP to invalid destination is handled gracefully."""
        from qubitcoin.qvm.opcodes import Opcode
        qvm = self._make_qvm()
        # JUMP to non-JUMPDEST location
        code = bytes([Opcode.PUSH1, 0xFF, Opcode.JUMP])
        result = qvm.execute(
            caller='0x' + 'a' * 40,
            address='0x' + 'b' * 40,
            code=code,
            gas=100000,
        )
        assert result.success is False

    def test_deep_memory_access(self):
        """Large memory offset is handled without crash."""
        from qubitcoin.qvm.opcodes import Opcode
        qvm = self._make_qvm()
        # Try to MSTORE at a large offset (should fail on gas, not crash)
        code = bytes([
            Opcode.PUSH1, 42,        # value
            Opcode.PUSH4,            # 4-byte offset
            0x00, 0x10, 0x00, 0x00,  # offset = 1,048,576
            Opcode.MSTORE,
            Opcode.STOP,
        ])
        result = qvm.execute(
            caller='0x' + 'a' * 40,
            address='0x' + 'b' * 40,
            code=code,
            gas=10_000_000,
        )
        # Either succeeds (enough gas for memory expansion) or fails (OOG)
        assert isinstance(result.success, bool)


class TestArithmeticEdgeCases:
    """Fuzz arithmetic opcodes with edge case values."""

    def _make_qvm(self):
        from qubitcoin.qvm.vm import QVM
        return QVM(db_manager=None, quantum_engine=None)

    def _exec_binary_op(self, qvm, opcode, a, b):
        """Execute a binary operation: PUSH b, PUSH a, OP, RETURN."""
        from qubitcoin.qvm.opcodes import Opcode
        # Encode a and b as 32-byte big-endian
        a_bytes = a.to_bytes(32, 'big')
        b_bytes = b.to_bytes(32, 'big')
        code = (
            bytes([Opcode.PUSH32]) + b_bytes +
            bytes([Opcode.PUSH32]) + a_bytes +
            bytes([opcode]) +
            bytes([Opcode.PUSH1, 0, Opcode.MSTORE,
                   Opcode.PUSH1, 32, Opcode.PUSH1, 0, Opcode.RETURN])
        )
        return qvm.execute(
            caller='0x' + 'a' * 40,
            address='0x' + 'b' * 40,
            code=code,
            gas=1_000_000,
        )

    def test_add_max_values(self):
        """ADD with max uint256 values wraps correctly."""
        from qubitcoin.qvm.opcodes import Opcode
        qvm = self._make_qvm()
        max_val = (1 << 256) - 1
        result = self._exec_binary_op(qvm, Opcode.ADD, max_val, 1)
        assert result.success is True
        val = int.from_bytes(result.return_data, 'big')
        assert val == 0  # overflow wraps to 0

    def test_sub_underflow(self):
        """SUB with underflow wraps correctly."""
        from qubitcoin.qvm.opcodes import Opcode
        qvm = self._make_qvm()
        result = self._exec_binary_op(qvm, Opcode.SUB, 0, 1)
        assert result.success is True
        val = int.from_bytes(result.return_data, 'big')
        assert val == (1 << 256) - 1  # wraps to max

    def test_div_by_zero(self):
        """DIV by zero returns 0 (EVM spec)."""
        from qubitcoin.qvm.opcodes import Opcode
        qvm = self._make_qvm()
        result = self._exec_binary_op(qvm, Opcode.DIV, 42, 0)
        assert result.success is True
        val = int.from_bytes(result.return_data, 'big')
        assert val == 0

    def test_mod_by_zero(self):
        """MOD by zero returns 0 (EVM spec)."""
        from qubitcoin.qvm.opcodes import Opcode
        qvm = self._make_qvm()
        result = self._exec_binary_op(qvm, Opcode.MOD, 42, 0)
        assert result.success is True
        val = int.from_bytes(result.return_data, 'big')
        assert val == 0

    def test_mul_large_values(self):
        """MUL with large values wraps at 2^256."""
        from qubitcoin.qvm.opcodes import Opcode
        qvm = self._make_qvm()
        large = (1 << 128)
        result = self._exec_binary_op(qvm, Opcode.MUL, large, large)
        assert result.success is True
        # (2^128)^2 = 2^256 ≡ 0 mod 2^256
        val = int.from_bytes(result.return_data, 'big')
        assert val == 0

    def test_exp_zero_zero(self):
        """EXP(0, 0) = 1 (mathematical convention)."""
        from qubitcoin.qvm.opcodes import Opcode
        qvm = self._make_qvm()
        result = self._exec_binary_op(qvm, Opcode.EXP, 0, 0)
        assert result.success is True
        val = int.from_bytes(result.return_data, 'big')
        assert val == 1


class TestRandomSequenceFuzz:
    """Longer random sequences with mixed valid/invalid opcodes."""

    def _make_qvm(self):
        from qubitcoin.qvm.vm import QVM
        return QVM(db_manager=None, quantum_engine=None)

    def test_mixed_valid_invalid_opcodes(self):
        """Mix of valid arithmetic and invalid bytes doesn't crash."""
        from qubitcoin.qvm.opcodes import Opcode
        qvm = self._make_qvm()
        rng = random.Random(123)
        valid_ops = [Opcode.ADD, Opcode.MUL, Opcode.SUB, Opcode.POP,
                     Opcode.PUSH1, Opcode.DUP1, Opcode.SWAP1]

        for _ in range(50):
            code_parts = []
            for _ in range(rng.randint(5, 30)):
                if rng.random() < 0.7:
                    op = rng.choice(valid_ops)
                    code_parts.append(op)
                    if op == Opcode.PUSH1:
                        code_parts.append(rng.randint(0, 255))
                else:
                    code_parts.append(rng.randint(0, 255))
            code_parts.append(Opcode.STOP)
            code = bytes(code_parts)
            result = qvm.execute(
                caller='0x' + 'a' * 40,
                address='0x' + 'b' * 40,
                code=code,
                gas=1_000_000,
            )
            assert isinstance(result.success, bool)

    def test_revert_after_computation(self):
        """REVERT opcode returns failure cleanly."""
        from qubitcoin.qvm.opcodes import Opcode
        qvm = self._make_qvm()
        code = bytes([
            Opcode.PUSH1, 5,
            Opcode.PUSH1, 3,
            Opcode.ADD,
            Opcode.PUSH1, 0, Opcode.MSTORE,
            Opcode.PUSH1, 32, Opcode.PUSH1, 0,
            Opcode.REVERT,
        ])
        result = qvm.execute(
            caller='0x' + 'a' * 40,
            address='0x' + 'b' * 40,
            code=code,
            gas=100000,
        )
        assert result.success is False
        assert len(result.return_data) == 32

    def test_zero_gas_execution(self):
        """Execution with 0 gas fails gracefully."""
        from qubitcoin.qvm.opcodes import Opcode
        qvm = self._make_qvm()
        code = bytes([Opcode.PUSH1, 1, Opcode.STOP])
        result = qvm.execute(
            caller='0x' + 'a' * 40,
            address='0x' + 'b' * 40,
            code=code,
            gas=0,
        )
        assert result.success is False
