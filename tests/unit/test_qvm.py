"""Unit tests for QVM (Quantum Virtual Machine) — opcodes, execution, precompiles."""
import pytest
from unittest.mock import MagicMock


class TestOpcodeDefinitions:
    """Test opcode constants and gas costs."""

    def test_opcode_enum_imports(self):
        from qubitcoin.qvm.opcodes import Opcode
        assert Opcode.STOP == 0x00
        assert Opcode.ADD == 0x01
        assert Opcode.RETURN == 0xF3
        assert Opcode.REVERT == 0xFD

    def test_quantum_opcodes_range(self):
        """Quantum opcodes are in 0xD0-0xD9 range."""
        from qubitcoin.qvm.opcodes import Opcode
        quantum_ops = [
            Opcode.QGATE, Opcode.QMEASURE, Opcode.QENTANGLE,
            Opcode.QSUPERPOSE, Opcode.QVQE, Opcode.QHAMILTONIAN,
            Opcode.QENERGY, Opcode.QPROOF, Opcode.QFIDELITY, Opcode.QDILITHIUM,
        ]
        for op in quantum_ops:
            assert 0xD0 <= op <= 0xDF, f"Quantum opcode {op:#x} out of range"

    def test_gas_costs_exist(self):
        """Every opcode has a gas cost defined."""
        from qubitcoin.qvm.opcodes import Opcode, GAS_COSTS
        key_ops = [Opcode.ADD, Opcode.MUL, Opcode.SLOAD, Opcode.SSTORE,
                   Opcode.CALL, Opcode.CREATE, Opcode.QVQE]
        for op in key_ops:
            assert op in GAS_COSTS, f"No gas cost for {op:#x}"
            assert GAS_COSTS[op] > 0 or op == Opcode.STOP

    def test_quantum_gas_higher_than_arithmetic(self):
        """Quantum opcodes cost more gas than basic arithmetic."""
        from qubitcoin.qvm.opcodes import GAS_COSTS, Opcode
        assert GAS_COSTS[Opcode.QVQE] > GAS_COSTS[Opcode.ADD]
        assert GAS_COSTS[Opcode.QENTANGLE] > GAS_COSTS[Opcode.MUL]

    def test_push_dup_swap_gas(self):
        """PUSH/DUP/SWAP opcodes all cost 3 gas."""
        from qubitcoin.qvm.opcodes import GAS_COSTS
        for i in range(0x60, 0x80):  # PUSH1-PUSH32
            assert GAS_COSTS[i] == 3
        for i in range(0x80, 0x90):  # DUP1-DUP16
            assert GAS_COSTS[i] == 3
        for i in range(0x90, 0xA0):  # SWAP1-SWAP16
            assert GAS_COSTS[i] == 3

    def test_uint256_bounds(self):
        """MAX_UINT256 and signed conversion helpers."""
        from qubitcoin.qvm.opcodes import MAX_UINT256, to_signed, to_unsigned
        assert MAX_UINT256 == (1 << 256) - 1
        assert to_signed(0) == 0
        assert to_signed(MAX_UINT256) == -1
        assert to_unsigned(-1) == MAX_UINT256

    def test_get_gas_cost_helper(self):
        from qubitcoin.qvm.opcodes import get_gas_cost, Opcode
        assert get_gas_cost(Opcode.ADD) == 3
        assert get_gas_cost(0xCF) == 0  # unknown opcode returns 0


class TestExecutionContext:
    """Test QVM execution context (stack, memory)."""

    def _make_ctx(self, code: bytes = b'', gas: int = 100000):
        from qubitcoin.qvm.vm import ExecutionContext
        return ExecutionContext(
            caller='0x' + 'a' * 40,
            address='0x' + 'b' * 40,
            origin='0x' + 'a' * 40,
            gas=gas,
            value=0,
            data=b'',
            code=code,
        )

    def test_push_pop(self):
        ctx = self._make_ctx()
        ctx.push(42)
        assert ctx.pop() == 42

    def test_stack_underflow(self):
        from qubitcoin.qvm.vm import StackUnderflowError
        ctx = self._make_ctx()
        with pytest.raises(StackUnderflowError):
            ctx.pop()

    def test_stack_overflow(self):
        from qubitcoin.qvm.vm import ExecutionError
        ctx = self._make_ctx()
        for i in range(1024):
            ctx.push(i)
        with pytest.raises(ExecutionError, match="Stack overflow"):
            ctx.push(1025)

    def test_push_uint256_mask(self):
        """Push values are masked to 256 bits."""
        from qubitcoin.qvm.opcodes import MAX_UINT256
        ctx = self._make_ctx()
        ctx.push(MAX_UINT256 + 1)
        assert ctx.pop() == 0  # overflow wraps to 0

    def test_memory_extend(self):
        """Memory extends with gas cost."""
        ctx = self._make_ctx(gas=1000000)
        ctx.memory_write(0, b'\x01\x02\x03')
        data = ctx.memory_read(0, 3)
        assert data == b'\x01\x02\x03'

    def test_memory_extend_word_aligned(self):
        """Memory always extends to 32-byte word boundary."""
        ctx = self._make_ctx(gas=1000000)
        ctx.memory_extend(0, 1)  # Request 1 byte
        assert len(ctx.memory) == 32  # Aligned to word

    def test_gas_consumption(self):
        ctx = self._make_ctx(gas=100)
        ctx.use_gas(50)
        assert ctx.gas_used == 50
        ctx.use_gas(50)
        assert ctx.gas_used == 100

    def test_out_of_gas(self):
        from qubitcoin.qvm.vm import OutOfGasError
        ctx = self._make_ctx(gas=10)
        with pytest.raises(OutOfGasError):
            ctx.use_gas(11)

    def test_jumpdest_analysis(self):
        """JUMPDEST positions are pre-analyzed."""
        from qubitcoin.qvm.opcodes import Opcode
        # PUSH1 0x00 JUMPDEST STOP
        code = bytes([Opcode.PUSH1, 0x00, Opcode.JUMPDEST, Opcode.STOP])
        ctx = self._make_ctx(code=code)
        assert 2 in ctx.valid_jumpdests
        assert 0 not in ctx.valid_jumpdests


class TestQVMExecution:
    """Test bytecode execution in the QVM."""

    def _make_qvm(self):
        from qubitcoin.qvm.vm import QVM
        return QVM(db_manager=None, quantum_engine=None)

    def test_stop(self):
        """STOP halts execution cleanly."""
        from qubitcoin.qvm.opcodes import Opcode
        qvm = self._make_qvm()
        code = bytes([Opcode.STOP])
        result = qvm.execute(caller='c', address='a', code=code, gas=1000)
        assert result.success is True

    def test_push1_stop(self):
        """PUSH1 pushes 1 byte and STOP halts."""
        from qubitcoin.qvm.opcodes import Opcode
        qvm = self._make_qvm()
        code = bytes([Opcode.PUSH1, 0x42, Opcode.STOP])
        result = qvm.execute(caller='c', address='a', code=code, gas=10000)
        assert result.success is True

    def test_add(self):
        """PUSH1 3 PUSH1 5 ADD should yield 8 on stack."""
        from qubitcoin.qvm.opcodes import Opcode
        qvm = self._make_qvm()
        # PUSH1 5, PUSH1 3, ADD, PUSH1 0, MSTORE, PUSH1 32, PUSH1 0, RETURN
        code = bytes([
            Opcode.PUSH1, 5,     # push 5
            Opcode.PUSH1, 3,     # push 3
            Opcode.ADD,          # 5 + 3 = 8
            Opcode.PUSH1, 0,     # memory offset
            Opcode.MSTORE,       # store result at offset 0
            Opcode.PUSH1, 32,    # size
            Opcode.PUSH1, 0,     # offset
            Opcode.RETURN,       # return 32 bytes from offset 0
        ])
        result = qvm.execute(caller='c', address='a', code=code, gas=100000)
        assert result.success is True
        assert len(result.return_data) == 32
        val = int.from_bytes(result.return_data, 'big')
        assert val == 8

    def test_mul(self):
        """PUSH1 6 PUSH1 7 MUL should yield 42."""
        from qubitcoin.qvm.opcodes import Opcode
        qvm = self._make_qvm()
        code = bytes([
            Opcode.PUSH1, 7,
            Opcode.PUSH1, 6,
            Opcode.MUL,
            Opcode.PUSH1, 0,
            Opcode.MSTORE,
            Opcode.PUSH1, 32,
            Opcode.PUSH1, 0,
            Opcode.RETURN,
        ])
        result = qvm.execute(caller='c', address='a', code=code, gas=100000)
        assert result.success is True
        val = int.from_bytes(result.return_data, 'big')
        assert val == 42

    def test_iszero(self):
        """ISZERO returns 1 for 0 input."""
        from qubitcoin.qvm.opcodes import Opcode
        qvm = self._make_qvm()
        code = bytes([
            Opcode.PUSH1, 0,
            Opcode.ISZERO,
            Opcode.PUSH1, 0,
            Opcode.MSTORE,
            Opcode.PUSH1, 32,
            Opcode.PUSH1, 0,
            Opcode.RETURN,
        ])
        result = qvm.execute(caller='c', address='a', code=code, gas=100000)
        assert result.success is True
        val = int.from_bytes(result.return_data, 'big')
        assert val == 1

    def test_revert(self):
        """REVERT marks execution as failed."""
        from qubitcoin.qvm.opcodes import Opcode
        qvm = self._make_qvm()
        code = bytes([
            Opcode.PUSH1, 0,   # size
            Opcode.PUSH1, 0,   # offset
            Opcode.REVERT,
        ])
        result = qvm.execute(caller='c', address='a', code=code, gas=100000)
        assert result.success is False

    def test_gas_tracking(self):
        """Gas used is tracked across operations."""
        from qubitcoin.qvm.opcodes import Opcode
        qvm = self._make_qvm()
        code = bytes([Opcode.PUSH1, 1, Opcode.PUSH1, 2, Opcode.ADD, Opcode.STOP])
        result = qvm.execute(caller='c', address='a', code=code, gas=100000)
        assert result.success is True
        assert result.gas_used > 0

    def test_out_of_gas_fails(self):
        """Execution fails when gas runs out."""
        from qubitcoin.qvm.opcodes import Opcode
        qvm = self._make_qvm()
        # SSTORE costs 20000 gas — give only 100
        code = bytes([
            Opcode.PUSH1, 1,   # value
            Opcode.PUSH1, 0,   # key
            Opcode.SSTORE,
            Opcode.STOP,
        ])
        result = qvm.execute(caller='c', address='a', code=code, gas=100)
        assert result.success is False

    def test_max_call_depth(self):
        """Execution at depth > 1024 is rejected."""
        qvm = self._make_qvm()
        result = qvm.execute(
            caller='c', address='a', code=b'\x00', gas=1000, depth=1025,
        )
        assert result.success is False
        assert 'depth' in result.revert_reason.lower()

    def test_calldatasize(self):
        """CALLDATASIZE returns length of input data."""
        from qubitcoin.qvm.opcodes import Opcode
        qvm = self._make_qvm()
        calldata = b'\xaa\xbb\xcc\xdd'
        code = bytes([
            Opcode.CALLDATASIZE,
            Opcode.PUSH1, 0,
            Opcode.MSTORE,
            Opcode.PUSH1, 32,
            Opcode.PUSH1, 0,
            Opcode.RETURN,
        ])
        result = qvm.execute(
            caller='c', address='a', code=code, data=calldata, gas=100000,
        )
        assert result.success is True
        val = int.from_bytes(result.return_data, 'big')
        assert val == 4


class TestQVMPrecompiles:
    """Test EVM precompiled contracts."""

    def _make_qvm(self):
        from qubitcoin.qvm.vm import QVM
        return QVM(db_manager=None, quantum_engine=None)

    def test_sha256_precompile(self):
        """Precompile 0x02: SHA-256."""
        import hashlib
        qvm = self._make_qvm()
        data = b'hello'
        result = qvm._execute_precompile(2, data, gas=10000)
        assert result.success is True
        assert result.return_data == hashlib.sha256(data).digest()

    def test_identity_precompile(self):
        """Precompile 0x04: identity (data copy)."""
        qvm = self._make_qvm()
        data = b'\x01\x02\x03\x04'
        result = qvm._execute_precompile(4, data, gas=10000)
        assert result.success is True
        assert result.return_data == data

    def test_modexp_precompile(self):
        """Precompile 0x05: modexp (base^exp % mod)."""
        qvm = self._make_qvm()
        # 2^10 mod 1000 = 1024 mod 1000 = 24
        b_len = (1).to_bytes(32, 'big')
        e_len = (1).to_bytes(32, 'big')
        m_len = (2).to_bytes(32, 'big')
        base = (2).to_bytes(1, 'big')
        exp = (10).to_bytes(1, 'big')
        mod = (1000).to_bytes(2, 'big')
        data = b_len + e_len + m_len + base + exp + mod
        result = qvm._execute_precompile(5, data, gas=10000)
        assert result.success is True
        val = int.from_bytes(result.return_data, 'big')
        assert val == 24

    def test_ecrecover_precompile(self):
        """Precompile 0x01: ecRecover returns 32 bytes."""
        qvm = self._make_qvm()
        data = b'\x00' * 128
        result = qvm._execute_precompile(1, data, gas=10000)
        assert result.success is True
        assert len(result.return_data) == 32

    def test_precompile_out_of_gas(self):
        """Precompile fails when insufficient gas."""
        qvm = self._make_qvm()
        result = qvm._execute_precompile(2, b'data', gas=1)  # SHA256 costs 60+
        assert result.success is False

    def test_ripemd160_precompile(self):
        """Precompile 0x03: RIPEMD-160 returns 32 bytes (left-padded)."""
        qvm = self._make_qvm()
        result = qvm._execute_precompile(3, b'hello', gas=100000)
        assert result.success is True
        assert len(result.return_data) == 32
        assert result.return_data[:12] == b'\x00' * 12  # left-padded


class TestQVMClasses:
    """Test ExecutionResult and error classes."""

    def test_execution_result_defaults(self):
        from qubitcoin.qvm.vm import ExecutionResult
        r = ExecutionResult()
        assert r.success is True
        assert r.return_data == b''
        assert r.gas_used == 0
        assert r.logs == []

    def test_execution_error_hierarchy(self):
        from qubitcoin.qvm.vm import (
            ExecutionError, OutOfGasError, StackUnderflowError, InvalidJumpError,
        )
        assert issubclass(OutOfGasError, ExecutionError)
        assert issubclass(StackUnderflowError, ExecutionError)
        assert issubclass(InvalidJumpError, ExecutionError)
