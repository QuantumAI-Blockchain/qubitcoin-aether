"""Unit tests for QVM gas exhaustion attack resistance.

Verifies that the QVM properly meters gas under adversarial conditions:
- Infinite loops exhaust gas
- Memory expansion is metered
- Large stack operations are bounded
- Recursive calls consume gas progressively
"""
import pytest
from unittest.mock import MagicMock


def _make_vm():
    """Create a QVM instance with mock DB."""
    from qubitcoin.qvm.vm import QVM
    db = MagicMock()
    db.get_contract_bytecode = MagicMock(return_value=None)
    db.get_storage = MagicMock(return_value='0')
    db.get_account = MagicMock(return_value=None)
    return QVM(db)


class TestInfiniteLoopGasExhaustion:
    """Test that infinite loops exhaust gas and fail gracefully."""

    def test_tight_loop_runs_out_of_gas(self):
        """JUMP back to JUMPDEST in tight loop exhausts gas."""
        vm = _make_vm()
        # JUMPDEST (0x5b), PUSH1 0x00 (0x60 0x00), JUMP (0x56)
        # This loops infinitely: PC=0 -> JUMPDEST -> PUSH 0 -> JUMP to 0
        code = bytes([0x5b, 0x60, 0x00, 0x56])
        result = vm.execute("caller", "contract", code, gas=10000)
        assert result.success is False
        assert result.gas_used > 0

    def test_push_pop_loop_exhausts_gas(self):
        """Repeated PUSH1/POP loop should exhaust gas."""
        vm = _make_vm()
        # JUMPDEST, PUSH1 0xFF, POP, PUSH1 0x00, JUMP
        code = bytes([0x5b, 0x60, 0xFF, 0x50, 0x60, 0x00, 0x56])
        result = vm.execute("caller", "contract", code, gas=5000)
        assert result.success is False

    def test_add_loop_exhausts_gas(self):
        """Arithmetic loop consuming gas via ADD."""
        vm = _make_vm()
        # PUSH1 1, PUSH1 1, JUMPDEST, ADD, DUP1, PUSH1 0x04, JUMP
        # offset 0: PUSH1 1
        # offset 2: PUSH1 1
        # offset 4: JUMPDEST
        # offset 5: ADD
        # offset 6: DUP1
        # offset 7: PUSH1 0x04
        # offset 9: JUMP
        code = bytes([0x60, 0x01, 0x60, 0x01, 0x5b, 0x01, 0x80, 0x60, 0x04, 0x56])
        result = vm.execute("caller", "contract", code, gas=2000)
        assert result.success is False


class TestMemoryExpansionGas:
    """Test gas metering for memory expansion."""

    def test_large_mstore_costs_gas(self):
        """Storing at a high memory offset costs expansion gas."""
        vm = _make_vm()
        # PUSH1 0x42, PUSH2 0xFFFF (offset 65535), MSTORE
        code = bytes([
            0x60, 0x42,             # PUSH1 value
            0x61, 0xFF, 0xFF,       # PUSH2 65535 (offset)
            0x52,                   # MSTORE
            0x00,                   # STOP
        ])
        result = vm.execute("caller", "contract", code, gas=100000)
        # Should succeed but consume significant gas for 64KB memory
        assert result.success is True
        assert result.gas_used > 1000  # Non-trivial gas for memory expansion

    def test_memory_expansion_fails_with_low_gas(self):
        """Large memory expansion with insufficient gas fails."""
        vm = _make_vm()
        # PUSH1 0x42, PUSH2 0xFFFF, MSTORE — needs lots of expansion gas
        code = bytes([0x60, 0x42, 0x61, 0xFF, 0xFF, 0x52, 0x00])
        result = vm.execute("caller", "contract", code, gas=100)
        assert result.success is False

    def test_zero_offset_mstore_minimal_gas(self):
        """MSTORE at offset 0 with fresh memory uses minimal expansion gas."""
        vm = _make_vm()
        # PUSH1 0x42, PUSH1 0x00, MSTORE, STOP
        code = bytes([0x60, 0x42, 0x60, 0x00, 0x52, 0x00])
        result = vm.execute("caller", "contract", code, gas=100000)
        assert result.success is True
        # Base gas + minimal memory expansion
        assert result.gas_used < 100


class TestStackBoundary:
    """Test stack overflow protection."""

    def test_stack_overflow_at_1024(self):
        """Pushing 1025 items should fail with stack overflow."""
        vm = _make_vm()
        # Build bytecode with 1025 PUSH1 instructions
        code = bytes([0x60, 0x01] * 1025)  # 1025 x PUSH1 1
        result = vm.execute("caller", "contract", code, gas=100000)
        assert result.success is False

    def test_stack_at_1024_succeeds(self):
        """Pushing exactly 1024 items should succeed."""
        vm = _make_vm()
        # 1024 x PUSH1 1 + STOP
        code = bytes([0x60, 0x01] * 1024) + bytes([0x00])
        result = vm.execute("caller", "contract", code, gas=1000000)
        assert result.success is True

    def test_stack_underflow_on_empty(self):
        """POP on empty stack should fail."""
        vm = _make_vm()
        code = bytes([0x50])  # POP with nothing on stack
        result = vm.execute("caller", "contract", code, gas=100000)
        assert result.success is False


class TestKeccak256GasScaling:
    """Test that Keccak256 gas scales with input size."""

    def test_keccak_small_input(self):
        """Small keccak input uses base gas."""
        vm = _make_vm()
        # PUSH1 0xAA, PUSH1 0x00, MSTORE8, PUSH1 1 (size), PUSH1 0 (offset), KECCAK256
        code = bytes([
            0x60, 0xAA, 0x60, 0x00, 0x53,  # MSTORE8
            0x60, 0x01, 0x60, 0x00, 0x20,  # KECCAK256(0, 1)
            0x60, 0x00, 0x52,              # MSTORE result
            0x60, 0x20, 0x60, 0x00, 0xf3,  # RETURN
        ])
        result = vm.execute("caller", "contract", code, gas=100000)
        assert result.success is True
        gas_small = result.gas_used

        # Larger input (32 bytes)
        code2 = bytes([
            0x60, 0x42, 0x60, 0x00, 0x52,  # MSTORE 32 bytes
            0x60, 0x20, 0x60, 0x00, 0x20,  # KECCAK256(0, 32)
            0x60, 0x00, 0x52,
            0x60, 0x20, 0x60, 0x00, 0xf3,
        ])
        result2 = vm.execute("caller", "contract", code2, gas=100000)
        assert result2.success is True
        gas_large = result2.gas_used

        # Larger input should cost more gas
        assert gas_large >= gas_small


class TestExpGasScaling:
    """Test that EXP gas scales with exponent byte length."""

    def test_exp_small_exponent_cheaper(self):
        """Small exponent (1 byte) uses less gas than large (32 bytes)."""
        vm = _make_vm()

        def _run_exp(base: int, exp: int) -> int:
            code = (
                bytes([0x7f]) + exp.to_bytes(32, 'big') +   # PUSH32 exp
                bytes([0x7f]) + base.to_bytes(32, 'big') +  # PUSH32 base
                bytes([0x0a]) +                              # EXP
                bytes([0x60, 0x00, 0x52]) +
                bytes([0x60, 0x20, 0x60, 0x00, 0xf3])
            )
            result = vm.execute("caller", "contract", code, gas=10000000)
            assert result.success is True
            return result.gas_used

        gas_small = _run_exp(2, 10)       # 10 = 1 byte
        gas_large = _run_exp(2, 1 << 250) # Very large exponent

        assert gas_large > gas_small


class TestCalldataCopyGas:
    """Test CALLDATACOPY gas scales with size."""

    def test_calldatacopy_zero_size_no_extra_gas(self):
        """CALLDATACOPY with size=0 uses minimal gas."""
        vm = _make_vm()
        # PUSH1 0 (size), PUSH1 0 (offset), PUSH1 0 (destOffset), CALLDATACOPY, STOP
        code = bytes([0x60, 0x00, 0x60, 0x00, 0x60, 0x00, 0x37, 0x00])
        result = vm.execute("caller", "contract", code, gas=100000)
        assert result.success is True
        gas_zero = result.gas_used

        # CALLDATACOPY 256 bytes
        code2 = bytes([0x61, 0x01, 0x00, 0x60, 0x00, 0x60, 0x00, 0x37, 0x00])
        result2 = vm.execute("caller", "contract", code2, gas=100000)
        assert result2.success is True

        assert result2.gas_used > gas_zero


class TestSstoreGas:
    """Test that SSTORE charges appropriate gas."""

    def test_sstore_charges_20000(self):
        """SSTORE from zero to non-zero charges 20,000 gas."""
        vm = _make_vm()
        # PUSH1 0x42 (value), PUSH1 0x00 (key), SSTORE, STOP
        code = bytes([0x60, 0x42, 0x60, 0x00, 0x55, 0x00])
        result = vm.execute("caller", "contract", code, gas=100000)
        assert result.success is True
        # SSTORE base cost is 20,000; total should be around 20,009+
        assert result.gas_used >= 20000

    def test_sstore_fails_with_insufficient_gas(self):
        """SSTORE with insufficient gas fails."""
        vm = _make_vm()
        code = bytes([0x60, 0x42, 0x60, 0x00, 0x55, 0x00])
        result = vm.execute("caller", "contract", code, gas=100)
        assert result.success is False


class TestGasOpcode:
    """Test the GAS opcode returns remaining gas."""

    def test_gas_opcode_returns_remaining(self):
        """GAS opcode should push remaining gas onto stack."""
        vm = _make_vm()
        # GAS (0x5a), PUSH1 0, MSTORE, PUSH1 32, PUSH1 0, RETURN
        code = bytes([0x5a, 0x60, 0x00, 0x52, 0x60, 0x20, 0x60, 0x00, 0xf3])
        result = vm.execute("caller", "contract", code, gas=100000)
        assert result.success is True
        remaining = int.from_bytes(result.return_data, 'big')
        # Remaining should be less than initial gas (some consumed before GAS opcode)
        assert remaining < 100000
        assert remaining > 0
