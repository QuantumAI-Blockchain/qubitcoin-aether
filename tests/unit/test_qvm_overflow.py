"""Unit tests for QVM integer overflow and underflow handling.

These tests verify that the QVM correctly handles uint256 boundary
conditions per the EVM spec — all arithmetic wraps modulo 2^256.
"""
import pytest
from unittest.mock import MagicMock


MAX_UINT256 = (1 << 256) - 1


def _make_vm():
    """Create a QVM instance with mock DB."""
    from qubitcoin.qvm.vm import QVM
    db = MagicMock()
    db.get_contract_bytecode = MagicMock(return_value=None)
    db.get_storage = MagicMock(return_value='0')
    db.get_account = MagicMock(return_value=None)
    return QVM(db)


def _push32(value: int) -> bytes:
    """Build PUSH32 instruction for a 256-bit value."""
    return bytes([0x7f]) + value.to_bytes(32, 'big')


def _exec_arith(vm, a: int, b: int, op_byte: int) -> int:
    """Execute a two-operand arithmetic op and return the result.

    Bytecode: PUSH32 b, PUSH32 a, OP, PUSH1 0, MSTORE, PUSH1 32, PUSH1 0, RETURN
    """
    code = (
        _push32(b) +        # PUSH32 b
        _push32(a) +        # PUSH32 a
        bytes([op_byte]) +  # OP
        bytes([0x60, 0x00, 0x52]) +  # MSTORE at offset 0
        bytes([0x60, 0x20, 0x60, 0x00, 0xf3])  # RETURN 32 bytes
    )
    result = vm.execute("caller", "contract", code, gas=1000000)
    assert result.success, f"Execution failed: {result.revert_reason}"
    return int.from_bytes(result.return_data, 'big')


class TestAddOverflow:
    """Test ADD wraps at uint256 boundary."""

    def test_add_normal(self):
        vm = _make_vm()
        assert _exec_arith(vm, 3, 5, 0x01) == 8

    def test_add_overflow_wraps(self):
        """MAX_UINT256 + 1 should wrap to 0."""
        vm = _make_vm()
        assert _exec_arith(vm, MAX_UINT256, 1, 0x01) == 0

    def test_add_overflow_wraps_larger(self):
        """MAX_UINT256 + 100 should wrap to 99."""
        vm = _make_vm()
        assert _exec_arith(vm, MAX_UINT256, 100, 0x01) == 99

    def test_add_max_plus_max(self):
        """MAX + MAX = MAX * 2 mod 2^256 = MAX - 1."""
        vm = _make_vm()
        expected = (MAX_UINT256 + MAX_UINT256) & MAX_UINT256
        assert _exec_arith(vm, MAX_UINT256, MAX_UINT256, 0x01) == expected


class TestSubUnderflow:
    """Test SUB wraps at uint256 boundary."""

    def test_sub_normal(self):
        vm = _make_vm()
        assert _exec_arith(vm, 10, 3, 0x03) == 7

    def test_sub_underflow_wraps(self):
        """0 - 1 should wrap to MAX_UINT256."""
        vm = _make_vm()
        assert _exec_arith(vm, 0, 1, 0x03) == MAX_UINT256

    def test_sub_larger_underflow(self):
        """5 - 10 should wrap."""
        vm = _make_vm()
        expected = (5 - 10) & MAX_UINT256
        assert _exec_arith(vm, 5, 10, 0x03) == expected


class TestMulOverflow:
    """Test MUL wraps at uint256 boundary."""

    def test_mul_normal(self):
        vm = _make_vm()
        assert _exec_arith(vm, 7, 8, 0x02) == 56

    def test_mul_overflow_wraps(self):
        """Large multiplication overflows and wraps."""
        vm = _make_vm()
        a = 1 << 200
        b = 1 << 100
        expected = (a * b) & MAX_UINT256
        assert _exec_arith(vm, a, b, 0x02) == expected

    def test_mul_max_times_two(self):
        """MAX * 2 = MAX * 2 mod 2^256."""
        vm = _make_vm()
        expected = (MAX_UINT256 * 2) & MAX_UINT256
        assert _exec_arith(vm, MAX_UINT256, 2, 0x02) == expected


class TestDivByZero:
    """Test DIV and MOD by zero return 0 (EVM spec)."""

    def test_div_by_zero_returns_zero(self):
        vm = _make_vm()
        assert _exec_arith(vm, 100, 0, 0x04) == 0

    def test_mod_by_zero_returns_zero(self):
        vm = _make_vm()
        assert _exec_arith(vm, 100, 0, 0x06) == 0

    def test_sdiv_by_zero_returns_zero(self):
        vm = _make_vm()
        assert _exec_arith(vm, 100, 0, 0x05) == 0

    def test_smod_by_zero_returns_zero(self):
        vm = _make_vm()
        assert _exec_arith(vm, 100, 0, 0x07) == 0


class TestExpOverflow:
    """Test EXP with large values wraps correctly."""

    def test_exp_normal(self):
        vm = _make_vm()
        assert _exec_arith(vm, 2, 10, 0x0a) == 1024

    def test_exp_large_wraps(self):
        """2^256 should wrap to 0."""
        vm = _make_vm()
        assert _exec_arith(vm, 2, 256, 0x0a) == 0

    def test_exp_zero_power(self):
        """x^0 = 1 for any x."""
        vm = _make_vm()
        assert _exec_arith(vm, 12345, 0, 0x0a) == 1

    def test_exp_zero_base(self):
        """0^n = 0 for n > 0."""
        vm = _make_vm()
        assert _exec_arith(vm, 0, 100, 0x0a) == 0


class TestAddmodMulmod:
    """Test ADDMOD and MULMOD with three operands."""

    def _exec_three_op(self, vm, a: int, b: int, n: int, op: int) -> int:
        """Execute three-operand op: PUSH n, PUSH b, PUSH a, OP, ..."""
        code = (
            _push32(n) +
            _push32(b) +
            _push32(a) +
            bytes([op]) +
            bytes([0x60, 0x00, 0x52]) +
            bytes([0x60, 0x20, 0x60, 0x00, 0xf3])
        )
        result = vm.execute("caller", "contract", code, gas=1000000)
        assert result.success
        return int.from_bytes(result.return_data, 'big')

    def test_addmod_normal(self):
        vm = _make_vm()
        assert self._exec_three_op(vm, 10, 7, 6, 0x08) == (10 + 7) % 6

    def test_addmod_overflow_safe(self):
        """ADDMOD handles intermediate overflow (a+b exceeds uint256)."""
        vm = _make_vm()
        # (MAX + 1) % 3 = 0 % 3 = 0  BUT ADDMOD does (MAX + 1) without overflow, then mod 3
        # In EVM, ADDMOD computes (a + b) mod N with arbitrary precision
        result = self._exec_three_op(vm, MAX_UINT256, 1, 3, 0x08)
        # (2^256) mod 3 = 1 (since 2^256 = MAX+1)
        assert result == (MAX_UINT256 + 1) % 3

    def test_addmod_by_zero_returns_zero(self):
        vm = _make_vm()
        assert self._exec_three_op(vm, 10, 5, 0, 0x08) == 0

    def test_mulmod_normal(self):
        vm = _make_vm()
        assert self._exec_three_op(vm, 10, 7, 6, 0x09) == (10 * 7) % 6

    def test_mulmod_by_zero_returns_zero(self):
        vm = _make_vm()
        assert self._exec_three_op(vm, 10, 5, 0, 0x09) == 0


class TestSignedArithmetic:
    """Test signed division and modulo edge cases."""

    def test_sdiv_negative_result(self):
        """Signed division of positive by negative."""
        from qubitcoin.qvm.opcodes import to_unsigned
        vm = _make_vm()
        # -1 in two's complement
        neg_one = MAX_UINT256  # 0xFF...FF
        result = _exec_arith(vm, 10, neg_one, 0x05)
        # 10 / (-1) = -10
        expected = to_unsigned(-10)
        assert result == expected

    def test_smod_with_negatives(self):
        """Signed modulo preserves sign of dividend."""
        from qubitcoin.qvm.opcodes import to_unsigned, to_signed
        vm = _make_vm()
        neg_seven = to_unsigned(-7)
        result = _exec_arith(vm, neg_seven, 3, 0x07)
        # -7 mod 3: sign follows dividend, so -1
        expected = to_unsigned(-1)
        assert result == expected


class TestShiftOverflow:
    """Test SHL/SHR with extreme shift values."""

    def test_shl_by_256_returns_zero(self):
        """Left shift by >= 256 returns 0."""
        vm = _make_vm()
        # SHL: shift=256, val=1 → 0
        code = (
            _push32(1) +        # val
            _push32(256) +      # shift
            bytes([0x1b]) +     # SHL
            bytes([0x60, 0x00, 0x52, 0x60, 0x20, 0x60, 0x00, 0xf3])
        )
        result = vm.execute("caller", "contract", code, gas=1000000)
        assert result.success
        assert int.from_bytes(result.return_data, 'big') == 0

    def test_shr_by_256_returns_zero(self):
        """Right shift by >= 256 returns 0."""
        vm = _make_vm()
        code = (
            _push32(MAX_UINT256) +
            _push32(256) +
            bytes([0x1c]) +     # SHR
            bytes([0x60, 0x00, 0x52, 0x60, 0x20, 0x60, 0x00, 0xf3])
        )
        result = vm.execute("caller", "contract", code, gas=1000000)
        assert result.success
        assert int.from_bytes(result.return_data, 'big') == 0

    def test_sar_negative_by_256_returns_all_ones(self):
        """Arithmetic right shift of -1 by 256 returns -1 (all ones)."""
        vm = _make_vm()
        code = (
            _push32(MAX_UINT256) +  # -1 in signed
            _push32(256) +
            bytes([0x1d]) +     # SAR
            bytes([0x60, 0x00, 0x52, 0x60, 0x20, 0x60, 0x00, 0xf3])
        )
        result = vm.execute("caller", "contract", code, gas=1000000)
        assert result.success
        assert int.from_bytes(result.return_data, 'big') == MAX_UINT256
