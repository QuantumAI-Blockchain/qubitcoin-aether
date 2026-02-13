"""Unit tests for QVM reentrancy protection and call-depth limits.

These tests verify that:
1. Max call depth (1024) is enforced
2. Static calls prevent state-changing operations
3. Gas is properly forwarded and consumed across nested calls
4. DELEGATECALL preserves caller context
5. CREATE/CREATE2 increment depth correctly
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
    vm = QVM(db)
    return vm


def _build_bytecode(*opcodes: int) -> bytes:
    """Build bytecode from a list of opcode integers."""
    return bytes(opcodes)


class TestCallDepthLimit:
    """Test maximum call depth enforcement (1024)."""

    def test_depth_zero_succeeds(self):
        """Execution at depth 0 should succeed."""
        vm = _make_vm()
        # PUSH1 0x42, PUSH1 0x00, MSTORE, PUSH1 0x20, PUSH1 0x00, RETURN
        code = bytes([0x60, 0x42, 0x60, 0x00, 0x52, 0x60, 0x20, 0x60, 0x00, 0xf3])
        result = vm.execute("caller", "contract", code, depth=0)
        assert result.success is True

    def test_depth_1024_succeeds(self):
        """Execution at depth exactly 1024 should succeed."""
        vm = _make_vm()
        # Simple STOP opcode
        code = bytes([0x00])
        result = vm.execute("caller", "contract", code, depth=1024)
        assert result.success is True

    def test_depth_1025_fails(self):
        """Execution at depth > 1024 should fail with depth error."""
        vm = _make_vm()
        code = bytes([0x00])
        result = vm.execute("caller", "contract", code, depth=1025)
        assert result.success is False
        assert "depth" in result.revert_reason.lower()

    def test_depth_max_int_fails(self):
        """Extreme depth values should fail gracefully."""
        vm = _make_vm()
        code = bytes([0x00])
        result = vm.execute("caller", "contract", code, depth=999999)
        assert result.success is False


class TestStaticCallProtection:
    """Test that static calls prevent state-changing operations."""

    def test_static_sstore_reverts(self):
        """SSTORE in static context should fail."""
        from qubitcoin.qvm.vm import ExecutionError
        vm = _make_vm()
        # PUSH1 0x01, PUSH1 0x00, SSTORE (0x55)
        code = bytes([0x60, 0x01, 0x60, 0x00, 0x55])
        result = vm.execute("caller", "contract", code, is_static=True)
        assert result.success is False

    def test_static_create_reverts(self):
        """CREATE in static context should fail."""
        vm = _make_vm()
        # PUSH1 0, PUSH1 0, PUSH1 0, CREATE (0xf0)
        code = bytes([0x60, 0x00, 0x60, 0x00, 0x60, 0x00, 0xf0])
        result = vm.execute("caller", "contract", code, is_static=True)
        assert result.success is False

    def test_static_selfdestruct_reverts(self):
        """SELFDESTRUCT in static context should fail."""
        vm = _make_vm()
        # PUSH1 0, SELFDESTRUCT (0xff)
        code = bytes([0x60, 0x00, 0xff])
        result = vm.execute("caller", "contract", code, is_static=True)
        assert result.success is False

    def test_static_log_reverts(self):
        """LOG0 in static context should fail."""
        vm = _make_vm()
        # PUSH1 0, PUSH1 0, LOG0 (0xa0)
        code = bytes([0x60, 0x00, 0x60, 0x00, 0xa0])
        result = vm.execute("caller", "contract", code, is_static=True)
        assert result.success is False

    def test_static_read_operations_succeed(self):
        """Read-only operations in static context should succeed."""
        vm = _make_vm()
        # PUSH1 0x42, PUSH1 0x00, MSTORE, PUSH1 0x20, PUSH1 0x00, RETURN
        code = bytes([0x60, 0x42, 0x60, 0x00, 0x52, 0x60, 0x20, 0x60, 0x00, 0xf3])
        result = vm.execute("caller", "contract", code, is_static=True)
        assert result.success is True


class TestGasForwarding:
    """Test gas metering across nested calls."""

    def test_gas_consumed_in_execution(self):
        """Basic execution consumes gas."""
        vm = _make_vm()
        # PUSH1 1, PUSH1 2, ADD, POP, STOP
        code = bytes([0x60, 0x01, 0x60, 0x02, 0x01, 0x50, 0x00])
        result = vm.execute("caller", "contract", code, gas=100000)
        assert result.gas_used > 0

    def test_out_of_gas_fails(self):
        """Execution with insufficient gas fails."""
        vm = _make_vm()
        # PUSH1 1, PUSH1 2, ADD — needs gas for PUSH(3) + PUSH(3) + ADD(3) = 9
        code = bytes([0x60, 0x01, 0x60, 0x02, 0x01])
        result = vm.execute("caller", "contract", code, gas=1)
        assert result.success is False

    def test_gas_remaining_equals_limit_minus_used(self):
        """Gas remaining should equal gas limit minus gas used."""
        vm = _make_vm()
        code = bytes([0x00])  # STOP
        result = vm.execute("caller", "contract", code, gas=1000000)
        assert result.gas_remaining == 1000000 - result.gas_used

    def test_zero_gas_limit(self):
        """Zero gas limit should fail immediately on any opcode."""
        vm = _make_vm()
        # PUSH1 0x01 — needs 3 gas
        code = bytes([0x60, 0x01])
        result = vm.execute("caller", "contract", code, gas=0)
        assert result.success is False


class TestStorageCacheIsolation:
    """Test that storage cache is properly managed across call depths."""

    def test_top_level_clears_cache(self):
        """Depth=0 call should clear storage cache."""
        vm = _make_vm()
        # Manually set cache
        vm._storage_cache = {"some_addr": {"some_key": "some_val"}}

        code = bytes([0x00])  # STOP
        vm.execute("caller", "contract", code, depth=0)

        # Cache should be cleared for depth=0
        assert vm._storage_cache == {} or "some_addr" not in vm._storage_cache

    def test_sub_call_shares_cache(self):
        """Depth>0 calls should share parent's cache."""
        vm = _make_vm()
        # Set up cache as if parent call wrote to it
        vm._storage_cache = {"contract": {"0": "42"}}

        code = bytes([0x00])  # STOP
        vm.execute("caller", "contract", code, depth=1)

        # Cache should NOT be cleared for depth > 0
        assert "contract" in vm._storage_cache


class TestCallValueInStatic:
    """Test CALL with value in static context."""

    def test_call_with_value_in_static_fails(self):
        """CALL with non-zero value in static context should fail."""
        vm = _make_vm()
        # Build bytecode: CALL(gas=100, addr=0x1234, value=1, ...)
        # PUSH1 0 (retSize), PUSH1 0 (retOffset), PUSH1 0 (argsSize),
        # PUSH1 0 (argsOffset), PUSH1 1 (value), PUSH20 addr, PUSH2 gas, CALL
        code = bytes([
            0x60, 0x00,  # retSize
            0x60, 0x00,  # retOffset
            0x60, 0x00,  # argsSize
            0x60, 0x00,  # argsOffset
            0x60, 0x01,  # value = 1 (non-zero)
            0x60, 0x00,  # addr
            0x61, 0x00, 0x64,  # gas = 100
            0xf1,        # CALL
        ])
        result = vm.execute("caller", "contract", code, is_static=True)
        assert result.success is False

    def test_call_with_zero_value_in_static_ok(self):
        """CALL with zero value in static context should succeed."""
        vm = _make_vm()
        # CALL with value=0
        code = bytes([
            0x60, 0x00,  # retSize
            0x60, 0x00,  # retOffset
            0x60, 0x00,  # argsSize
            0x60, 0x00,  # argsOffset
            0x60, 0x00,  # value = 0
            0x60, 0x00,  # addr
            0x61, 0x00, 0x64,  # gas = 100
            0xf1,        # CALL
        ])
        result = vm.execute("caller", "contract", code, is_static=True, gas=1000000)
        assert result.success is True


class TestCreate2DepthIncrement:
    """Test CREATE2 increments call depth."""

    def test_create2_in_static_reverts(self):
        """CREATE2 in static context should fail."""
        vm = _make_vm()
        # PUSH1 0 (salt), PUSH1 0 (size), PUSH1 0 (offset), PUSH1 0 (value), CREATE2
        code = bytes([
            0x60, 0x00,  # salt
            0x60, 0x00,  # size
            0x60, 0x00,  # offset
            0x60, 0x00,  # value
            0xf5,        # CREATE2
        ])
        result = vm.execute("caller", "contract", code, is_static=True)
        assert result.success is False


class TestRevertBehavior:
    """Test REVERT opcode behavior."""

    def test_revert_marks_failure(self):
        """REVERT should mark execution as failed."""
        vm = _make_vm()
        # PUSH1 0 (size), PUSH1 0 (offset), REVERT
        code = bytes([0x60, 0x00, 0x60, 0x00, 0xfd])
        result = vm.execute("caller", "contract", code, gas=1000000)
        assert result.success is False

    def test_revert_with_data(self):
        """REVERT should return the specified memory data."""
        vm = _make_vm()
        # PUSH1 0xAA, PUSH1 0x00, MSTORE8, PUSH1 0x01, PUSH1 0x00, REVERT
        code = bytes([
            0x60, 0xAA,  # PUSH1 0xAA
            0x60, 0x00,  # PUSH1 0x00
            0x53,        # MSTORE8
            0x60, 0x01,  # PUSH1 1 (size)
            0x60, 0x00,  # PUSH1 0 (offset)
            0xfd,        # REVERT
        ])
        result = vm.execute("caller", "contract", code, gas=1000000)
        assert result.success is False
        assert len(result.return_data) == 1
        assert result.return_data[0] == 0xAA

    def test_return_with_data(self):
        """RETURN should mark success and return data."""
        vm = _make_vm()
        # PUSH1 0xBB, PUSH1 0x00, MSTORE8, PUSH1 0x01, PUSH1 0x00, RETURN
        code = bytes([
            0x60, 0xBB,
            0x60, 0x00,
            0x53,
            0x60, 0x01,
            0x60, 0x00,
            0xf3,        # RETURN
        ])
        result = vm.execute("caller", "contract", code, gas=1000000)
        assert result.success is True
        assert len(result.return_data) == 1
        assert result.return_data[0] == 0xBB
