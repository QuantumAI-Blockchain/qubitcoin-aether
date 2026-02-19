"""
Batch 46 Tests: QVM Debugger — Step-Through Execution with Breakpoints & State Inspection
  - QVMDebugger (qvm/debugger.py)
"""

import pytest

from qubitcoin.qvm.opcodes import Opcode


# ═══════════════════════════════════════════════════════════════════════
#  Helper — build bytecode from opcode sequences
# ═══════════════════════════════════════════════════════════════════════

def _bytes(*args: int) -> bytes:
    """Build bytecode from opcode ints."""
    return bytes(args)


def _make_debugger(**kwargs):
    from qubitcoin.qvm.debugger import QVMDebugger
    return QVMDebugger(**kwargs)


# Simple programs for testing
# PUSH1 5, PUSH1 3, ADD, STOP  → stack=[8], 4 opcodes
SIMPLE_ADD = _bytes(
    Opcode.PUSH1, 5,
    Opcode.PUSH1, 3,
    Opcode.ADD,
    Opcode.STOP,
)

# PUSH1 7, PUSH1 6, MUL, STOP → stack=[42]
SIMPLE_MUL = _bytes(
    Opcode.PUSH1, 7,
    Opcode.PUSH1, 6,
    Opcode.MUL,
    Opcode.STOP,
)

# PUSH1 4, PUSH1 10, SUB, STOP → stack=[6]  (SUB pops a=10 then b=4, result=a-b=6)
SIMPLE_SUB = _bytes(
    Opcode.PUSH1, 4,
    Opcode.PUSH1, 10,
    Opcode.SUB,
    Opcode.STOP,
)

# PUSH1 10, PUSH1 0, DIV, STOP → stack=[0] (div by zero)
DIV_BY_ZERO = _bytes(
    Opcode.PUSH1, 10,
    Opcode.PUSH1, 0,
    Opcode.DIV,
    Opcode.STOP,
)

# PUSH1 0, ISZERO, STOP → stack=[1]
ISZERO_PROG = _bytes(
    Opcode.PUSH1, 0,
    Opcode.ISZERO,
    Opcode.STOP,
)

# PUSH1 42, PUSH1 0, MSTORE, PUSH1 0, MLOAD, STOP → stack=[42]
MEMORY_PROG = _bytes(
    Opcode.PUSH1, 42,
    Opcode.PUSH1, 0,
    Opcode.MSTORE,
    Opcode.PUSH1, 0,
    Opcode.MLOAD,
    Opcode.STOP,
)

# PUSH1 99, PUSH1 0x10, SSTORE, PUSH1 0x10, SLOAD, STOP → stack=[99]
STORAGE_PROG = _bytes(
    Opcode.PUSH1, 99,
    Opcode.PUSH1, 0x10,
    Opcode.SSTORE,
    Opcode.PUSH1, 0x10,
    Opcode.SLOAD,
    Opcode.STOP,
)

# PUSH1 5, DUP1, ADD, STOP → stack=[10]
DUP_PROG = _bytes(
    Opcode.PUSH1, 5,
    Opcode.DUP1,
    Opcode.ADD,
    Opcode.STOP,
)

# PUSH1 1, PUSH1 2, SWAP1, STOP → stack=[1, 2] → after SWAP → stack=[2, 1]
SWAP_PROG = _bytes(
    Opcode.PUSH1, 1,
    Opcode.PUSH1, 2,
    Opcode.SWAP1,
    Opcode.STOP,
)

# PUSH2 0x01 0x00 (=256), STOP → stack=[256]
PUSH2_PROG = _bytes(
    Opcode.PUSH2, 0x01, 0x00,
    Opcode.STOP,
)

# PC, STOP → stack=[0] (PC at position 0)
PC_PROG = _bytes(
    Opcode.PC,
    Opcode.STOP,
)


# ═══════════════════════════════════════════════════════════════════════
#  Test: Load & Reset
# ═══════════════════════════════════════════════════════════════════════

class TestLoadReset:
    """Tests for loading bytecode and resetting debugger."""

    def test_load_bytecode_success(self):
        d = _make_debugger()
        result = d.load_bytecode(SIMPLE_ADD)
        assert result["success"] is True
        assert result["bytecode_size"] == len(SIMPLE_ADD)
        assert result["gas_limit"] == 1_000_000

    def test_load_bytecode_with_custom_gas(self):
        d = _make_debugger()
        result = d.load_bytecode(SIMPLE_ADD, gas_limit=500)
        assert result["gas_limit"] == 500

    def test_load_empty_bytecode(self):
        d = _make_debugger()
        result = d.load_bytecode(b"")
        assert result["success"] is True
        assert result["bytecode_size"] == 0

    def test_reset_preserves_breakpoints(self):
        d = _make_debugger()
        d.load_bytecode(SIMPLE_ADD)
        d.set_breakpoint(pc=2)
        d.step()  # Execute one opcode
        d.reset()
        bps = d.list_breakpoints()
        assert len(bps) == 1
        assert bps[0]["value"] == 2

    def test_load_clears_state(self):
        d = _make_debugger()
        d.load_bytecode(SIMPLE_ADD)
        d.step()
        d.step()
        d.load_bytecode(SIMPLE_MUL)
        assert d.get_stack() == []
        assert not d.is_halted()

    def test_initial_state(self):
        d = _make_debugger(gas_limit=5000)
        stats = d.get_stats()
        assert stats["bytecode_size"] == 0
        assert stats["gas_limit"] == 5000
        assert stats["step_count"] == 0


# ═══════════════════════════════════════════════════════════════════════
#  Test: Breakpoints
# ═══════════════════════════════════════════════════════════════════════

class TestBreakpoints:
    """Tests for breakpoint management."""

    def test_set_pc_breakpoint(self):
        d = _make_debugger()
        result = d.set_breakpoint(pc=4)
        assert result["success"] is True
        assert result["type"] == "pc"
        assert result["value"] == 4
        assert "bp_id" in result

    def test_set_opcode_breakpoint(self):
        d = _make_debugger()
        result = d.set_breakpoint(opcode=Opcode.ADD)
        assert result["type"] == "opcode"

    def test_set_gas_below_breakpoint(self):
        d = _make_debugger()
        result = d.set_breakpoint(gas_below=500)
        assert result["type"] == "gas_below"

    def test_set_stack_depth_breakpoint(self):
        d = _make_debugger()
        result = d.set_breakpoint(stack_depth=3)
        assert result["type"] == "stack_depth"

    def test_set_breakpoint_no_params(self):
        d = _make_debugger()
        result = d.set_breakpoint()
        assert result["success"] is False

    def test_remove_breakpoint(self):
        d = _make_debugger()
        bp = d.set_breakpoint(pc=0)
        result = d.remove_breakpoint(bp["bp_id"])
        assert result["success"] is True
        assert d.list_breakpoints() == []

    def test_remove_nonexistent_breakpoint(self):
        d = _make_debugger()
        result = d.remove_breakpoint(999)
        assert result["success"] is False

    def test_toggle_breakpoint(self):
        d = _make_debugger()
        bp = d.set_breakpoint(pc=0)
        bp_id = bp["bp_id"]
        result = d.toggle_breakpoint(bp_id)
        assert result["enabled"] is False
        result = d.toggle_breakpoint(bp_id)
        assert result["enabled"] is True

    def test_toggle_nonexistent(self):
        d = _make_debugger()
        result = d.toggle_breakpoint(999)
        assert result["success"] is False

    def test_list_multiple_breakpoints(self):
        d = _make_debugger()
        d.set_breakpoint(pc=0)
        d.set_breakpoint(pc=4)
        d.set_breakpoint(opcode=Opcode.STOP)
        bps = d.list_breakpoints()
        assert len(bps) == 3

    def test_disabled_breakpoint_not_hit(self):
        d = _make_debugger()
        d.load_bytecode(SIMPLE_ADD)
        bp = d.set_breakpoint(pc=4)  # at ADD
        d.toggle_breakpoint(bp["bp_id"])  # disable
        result = d.continue_execution()
        # Should run to completion without hitting disabled bp
        assert result["stopped_reason"] == "halted"

    def test_breakpoint_hit_count(self):
        d = _make_debugger()
        d.load_bytecode(SIMPLE_ADD)
        d.set_breakpoint(pc=2)  # break before PUSH1 3
        d.continue_execution()
        bps = d.list_breakpoints()
        assert bps[0]["hit_count"] == 1


# ═══════════════════════════════════════════════════════════════════════
#  Test: Step Execution
# ═══════════════════════════════════════════════════════════════════════

class TestStepExecution:
    """Tests for single-stepping through bytecode."""

    def test_step_push1(self):
        d = _make_debugger()
        d.load_bytecode(SIMPLE_ADD)
        result = d.step()  # PUSH1 5
        assert result["success"] is True
        assert result["opcode"] == "PUSH1"
        assert d.get_stack() == ["0x5"]

    def test_step_add(self):
        d = _make_debugger()
        d.load_bytecode(SIMPLE_ADD)
        d.step()  # PUSH1 5
        d.step()  # PUSH1 3
        result = d.step()  # ADD
        assert result["opcode"] == "ADD"
        assert d.get_stack() == ["0x8"]

    def test_step_stop_halts(self):
        d = _make_debugger()
        d.load_bytecode(SIMPLE_ADD)
        d.step()  # PUSH1 5
        d.step()  # PUSH1 3
        d.step()  # ADD
        result = d.step()  # STOP
        assert d.is_halted()

    def test_step_after_halt(self):
        d = _make_debugger()
        d.load_bytecode(_bytes(Opcode.STOP))
        d.step()  # STOP
        result = d.step()
        assert result["success"] is False
        assert result["halted"] is True

    def test_step_mul(self):
        d = _make_debugger()
        d.load_bytecode(SIMPLE_MUL)
        d.step()  # PUSH1 7
        d.step()  # PUSH1 6
        d.step()  # MUL
        assert d.get_stack() == [hex(42)]

    def test_step_sub(self):
        d = _make_debugger()
        d.load_bytecode(SIMPLE_SUB)
        d.step()  # PUSH1 10
        d.step()  # PUSH1 4
        d.step()  # SUB
        assert d.get_stack() == [hex(6)]

    def test_step_div_by_zero(self):
        d = _make_debugger()
        d.load_bytecode(DIV_BY_ZERO)
        d.step()  # PUSH1 10
        d.step()  # PUSH1 0
        d.step()  # DIV  (10/0 = 0 per EVM spec)
        assert d.get_stack() == ["0x0"]

    def test_step_iszero_true(self):
        d = _make_debugger()
        d.load_bytecode(ISZERO_PROG)
        d.step()  # PUSH1 0
        d.step()  # ISZERO
        assert d.get_stack() == ["0x1"]

    def test_step_iszero_false(self):
        d = _make_debugger()
        d.load_bytecode(_bytes(Opcode.PUSH1, 5, Opcode.ISZERO, Opcode.STOP))
        d.step()  # PUSH1 5
        d.step()  # ISZERO
        assert d.get_stack() == ["0x0"]

    def test_step_pop(self):
        d = _make_debugger()
        d.load_bytecode(_bytes(Opcode.PUSH1, 42, Opcode.POP, Opcode.STOP))
        d.step()  # PUSH1 42
        d.step()  # POP
        assert d.get_stack() == []

    def test_step_dup1(self):
        d = _make_debugger()
        d.load_bytecode(DUP_PROG)
        d.step()  # PUSH1 5
        d.step()  # DUP1
        assert d.get_stack() == ["0x5", "0x5"]

    def test_step_swap1(self):
        d = _make_debugger()
        d.load_bytecode(SWAP_PROG)
        d.step()  # PUSH1 1
        d.step()  # PUSH1 2
        d.step()  # SWAP1
        # After SWAP1: stack bottom is 2, top is 1
        assert d.get_stack() == ["0x2", "0x1"]

    def test_step_push2(self):
        d = _make_debugger()
        d.load_bytecode(PUSH2_PROG)
        d.step()  # PUSH2 0x0100
        assert d.get_stack() == [hex(256)]

    def test_step_pc(self):
        d = _make_debugger()
        d.load_bytecode(PC_PROG)
        d.step()  # PC
        assert d.get_stack() == ["0x0"]

    def test_step_gas_opcode(self):
        d = _make_debugger(gas_limit=10000)
        d.load_bytecode(_bytes(Opcode.GAS, Opcode.STOP))
        d.step()  # GAS
        stack = d.get_stack()
        # Gas should be remaining gas after GAS opcode executes
        assert len(stack) == 1

    def test_step_jumpdest(self):
        d = _make_debugger()
        d.load_bytecode(_bytes(Opcode.JUMPDEST, Opcode.STOP))
        d.step()  # JUMPDEST (no-op)
        assert d.get_stack() == []
        assert not d.is_halted()

    def test_step_gas_deduction(self):
        d = _make_debugger(gas_limit=100)
        d.load_bytecode(SIMPLE_ADD)
        d.step()  # PUSH1 (3 gas)
        stats = d.get_stats()
        assert stats["gas_used"] > 0

    def test_out_of_gas(self):
        d = _make_debugger(gas_limit=5)
        d.load_bytecode(SIMPLE_ADD)
        d.step()  # PUSH1 costs 3
        result = d.step()  # PUSH1 again costs 3, but only 2 gas left
        assert result["halted"] is True


# ═══════════════════════════════════════════════════════════════════════
#  Test: Memory Operations
# ═══════════════════════════════════════════════════════════════════════

class TestMemoryOps:
    """Tests for MLOAD/MSTORE memory operations."""

    def test_mstore_mload(self):
        d = _make_debugger()
        d.load_bytecode(MEMORY_PROG)
        for _ in range(7):
            d.step()
        # stack should have 42 from MLOAD
        assert d.get_stack() == [hex(42)]

    def test_memory_expansion(self):
        d = _make_debugger()
        d.load_bytecode(MEMORY_PROG)
        for _ in range(5):  # Up through MSTORE
            d.step()
        mem = d.get_memory()
        assert len(mem) > 0  # Memory was expanded

    def test_get_memory_hex(self):
        d = _make_debugger()
        d.load_bytecode(MEMORY_PROG)
        for _ in range(5):  # Through MSTORE
            d.step()
        mem_hex = d.get_memory(offset=0, length=32)
        # 42 stored as 32-byte big-endian
        assert mem_hex.endswith("2a")  # 42 = 0x2a


# ═══════════════════════════════════════════════════════════════════════
#  Test: Storage Operations
# ═══════════════════════════════════════════════════════════════════════

class TestStorageOps:
    """Tests for SLOAD/SSTORE storage operations."""

    def test_sstore_sload(self):
        d = _make_debugger()
        d.load_bytecode(STORAGE_PROG)
        for _ in range(7):
            d.step()
        assert d.get_stack() == [hex(99)]

    def test_storage_tracking(self):
        d = _make_debugger()
        d.load_bytecode(STORAGE_PROG)
        for _ in range(5):  # Through SSTORE
            d.step()
        storage = d.get_storage()
        assert len(storage) == 1
        assert hex(0x10) in storage

    def test_sload_nonexistent_returns_zero(self):
        d = _make_debugger()
        d.load_bytecode(_bytes(Opcode.PUSH1, 0xFF, Opcode.SLOAD, Opcode.STOP))
        d.step()  # PUSH1 0xFF
        d.step()  # SLOAD
        assert d.get_stack() == ["0x0"]


# ═══════════════════════════════════════════════════════════════════════
#  Test: Continue Execution
# ═══════════════════════════════════════════════════════════════════════

class TestContinueExecution:
    """Tests for continue_execution (run until breakpoint/halt)."""

    def test_continue_to_halt(self):
        d = _make_debugger()
        d.load_bytecode(SIMPLE_ADD)
        result = d.continue_execution()
        assert result["success"] is True
        assert result["stopped_reason"] == "halted"
        assert result["halted"] is True

    def test_continue_to_pc_breakpoint(self):
        d = _make_debugger()
        d.load_bytecode(SIMPLE_ADD)
        d.set_breakpoint(pc=4)  # Before ADD
        result = d.continue_execution()
        assert result["stopped_reason"] == "breakpoint"

    def test_continue_to_opcode_breakpoint(self):
        d = _make_debugger()
        d.load_bytecode(SIMPLE_ADD)
        d.set_breakpoint(opcode=Opcode.ADD)
        result = d.continue_execution()
        assert result["stopped_reason"] == "breakpoint"

    def test_continue_max_steps(self):
        # Build a long loop-like program: many JUMPDESTs
        ops = [Opcode.JUMPDEST] * 100 + [Opcode.STOP]
        d = _make_debugger()
        d.load_bytecode(bytes(ops))
        result = d.continue_execution(max_steps=10)
        assert result["stopped_reason"] == "max_steps"
        assert result["steps_executed"] == 10

    def test_continue_gas_breakpoint(self):
        d = _make_debugger(gas_limit=100)
        d.load_bytecode(SIMPLE_ADD)
        d.set_breakpoint(gas_below=95)
        result = d.continue_execution()
        assert result["stopped_reason"] == "breakpoint"

    def test_continue_stack_depth_breakpoint(self):
        d = _make_debugger()
        d.load_bytecode(SIMPLE_ADD)
        d.set_breakpoint(stack_depth=2)  # break when 2+ items on stack
        result = d.continue_execution()
        assert result["stopped_reason"] == "breakpoint"

    def test_continue_then_step(self):
        d = _make_debugger()
        d.load_bytecode(SIMPLE_ADD)
        d.set_breakpoint(pc=4)  # Before ADD
        d.continue_execution()
        result = d.step()  # Execute ADD
        assert result["success"] is True


# ═══════════════════════════════════════════════════════════════════════
#  Test: State Snapshots
# ═══════════════════════════════════════════════════════════════════════

class TestStateSnapshots:
    """Tests for state snapshot capture and inspection."""

    def test_take_snapshot(self):
        d = _make_debugger()
        d.load_bytecode(SIMPLE_ADD)
        d.step()  # PUSH1 5
        snap = d.take_snapshot()
        assert snap.snapshot_id is not None
        assert snap.pc == 2
        assert snap.stack == [5]

    def test_snapshot_immutability(self):
        d = _make_debugger()
        d.load_bytecode(SIMPLE_ADD)
        d.step()
        snap1 = d.take_snapshot()
        d.step()
        snap2 = d.take_snapshot()
        # snap1 should still have old state
        assert len(snap1.stack) == 1
        assert len(snap2.stack) == 2

    def test_snapshot_to_dict(self):
        d = _make_debugger()
        d.load_bytecode(SIMPLE_ADD)
        snap = d.take_snapshot()
        d = snap.to_dict()
        assert "snapshot_id" in d
        assert "stack_depth" in d
        assert "memory_size" in d

    def test_get_snapshots(self):
        d = _make_debugger()
        d.load_bytecode(SIMPLE_ADD)
        d.take_snapshot()
        d.step()
        d.take_snapshot()
        snaps = d.get_snapshots()
        assert len(snaps) == 2

    def test_snapshot_at_halt(self):
        d = _make_debugger()
        d.load_bytecode(SIMPLE_ADD)
        d.continue_execution()
        snap = d.take_snapshot()
        assert snap.halted is True


# ═══════════════════════════════════════════════════════════════════════
#  Test: Disassembly
# ═══════════════════════════════════════════════════════════════════════

class TestDisassembly:
    """Tests for bytecode disassembly."""

    def test_disassemble_simple(self):
        d = _make_debugger()
        d.load_bytecode(SIMPLE_ADD)
        ops = d.disassemble()
        assert len(ops) >= 4
        assert ops[0]["name"] == "PUSH1"
        assert ops[0]["push_data"] == "0x05"

    def test_disassemble_push2(self):
        d = _make_debugger()
        d.load_bytecode(PUSH2_PROG)
        ops = d.disassemble()
        assert ops[0]["name"] == "PUSH2"
        assert ops[0]["push_data"] == "0x0100"

    def test_disassemble_limit(self):
        d = _make_debugger()
        d.load_bytecode(bytes([Opcode.JUMPDEST] * 100 + [Opcode.STOP]))
        ops = d.disassemble(limit=5)
        assert len(ops) == 5

    def test_disassemble_start_offset(self):
        d = _make_debugger()
        d.load_bytecode(SIMPLE_ADD)
        ops = d.disassemble(start=4)  # Start at ADD
        assert ops[0]["name"] == "ADD"


# ═══════════════════════════════════════════════════════════════════════
#  Test: Execution Trace & Gas Profile
# ═══════════════════════════════════════════════════════════════════════

class TestTraceAndGasProfile:
    """Tests for execution trace and gas profiling."""

    def test_trace_records_steps(self):
        d = _make_debugger()
        d.load_bytecode(SIMPLE_ADD)
        d.continue_execution()
        trace = d.get_trace()
        assert len(trace) >= 3  # PUSH1, PUSH1, ADD, STOP

    def test_trace_step_format(self):
        d = _make_debugger()
        d.load_bytecode(SIMPLE_ADD)
        d.step()
        trace = d.get_trace()
        assert len(trace) == 1
        step = trace[0]
        assert "step" in step
        assert "pc" in step
        assert "opcode_name" in step
        assert "gas_cost" in step

    def test_trace_last_n(self):
        d = _make_debugger()
        d.load_bytecode(bytes([Opcode.JUMPDEST] * 20 + [Opcode.STOP]))
        d.continue_execution()
        trace = d.get_trace(last_n=5)
        assert len(trace) == 5

    def test_gas_profile(self):
        d = _make_debugger()
        d.load_bytecode(SIMPLE_ADD)
        d.continue_execution()
        profile = d.get_gas_profile()
        assert "opcodes" in profile
        assert "total_steps" in profile
        assert "total_gas_used" in profile
        assert profile["total_gas_used"] > 0

    def test_gas_profile_by_opcode(self):
        d = _make_debugger()
        d.load_bytecode(SIMPLE_ADD)
        d.continue_execution()
        profile = d.get_gas_profile()
        # Should have entries for PUSH1, ADD, STOP
        assert "PUSH1" in profile["opcodes"]
        assert "ADD" in profile["opcodes"]

    def test_gas_profile_counts(self):
        d = _make_debugger()
        d.load_bytecode(SIMPLE_ADD)
        d.continue_execution()
        profile = d.get_gas_profile()
        # Two PUSH1s
        assert profile["opcodes"]["PUSH1"]["count"] == 2


# ═══════════════════════════════════════════════════════════════════════
#  Test: JUMP Operations
# ═══════════════════════════════════════════════════════════════════════

class TestJumpOps:
    """Tests for JUMP and JUMPI opcodes."""

    def test_jump(self):
        # PUSH1 4, JUMP, INVALID, JUMPDEST, STOP
        prog = _bytes(
            Opcode.PUSH1, 4,
            Opcode.JUMP,
            Opcode.INVALID,
            Opcode.JUMPDEST,
            Opcode.STOP,
        )
        d = _make_debugger()
        d.load_bytecode(prog)
        d.continue_execution()
        assert d.is_halted()
        # Should reach STOP (didn't hit INVALID)
        stats = d.get_stats()
        assert stats["halted"] is True

    def test_jumpi_true(self):
        # PUSH1 1, PUSH1 5, JUMPI, INVALID, INVALID, JUMPDEST, STOP
        prog = _bytes(
            Opcode.PUSH1, 1,   # condition (true)
            Opcode.PUSH1, 6,   # destination
            Opcode.JUMPI,
            Opcode.INVALID,
            Opcode.JUMPDEST,
            Opcode.STOP,
        )
        d = _make_debugger()
        d.load_bytecode(prog)
        d.continue_execution()
        assert d.is_halted()

    def test_jumpi_false(self):
        # PUSH1 0 (false condition), PUSH1 6, JUMPI, STOP, ...
        prog = _bytes(
            Opcode.PUSH1, 0,   # condition (false)
            Opcode.PUSH1, 6,   # destination
            Opcode.JUMPI,
            Opcode.STOP,
            Opcode.JUMPDEST,
            Opcode.STOP,
        )
        d = _make_debugger()
        d.load_bytecode(prog)
        d.continue_execution()
        assert d.is_halted()

    def test_invalid_jump_destination(self):
        prog = _bytes(
            Opcode.PUSH1, 0xFF,
            Opcode.JUMP,
        )
        d = _make_debugger()
        d.load_bytecode(prog)
        result = d.continue_execution()
        assert d.is_halted()  # Should error halt


# ═══════════════════════════════════════════════════════════════════════
#  Test: RETURN & REVERT
# ═══════════════════════════════════════════════════════════════════════

class TestReturnRevert:
    """Tests for RETURN and REVERT opcodes."""

    def test_return_opcode(self):
        # Store data in memory, then RETURN it
        prog = _bytes(
            Opcode.PUSH1, 0xAA,     # value
            Opcode.PUSH1, 0,        # offset
            Opcode.MSTORE,
            Opcode.PUSH1, 32,       # length
            Opcode.PUSH1, 0,        # offset
            Opcode.RETURN,
        )
        d = _make_debugger()
        d.load_bytecode(prog)
        d.continue_execution()
        assert d.is_halted()
        ret = d.get_return_data()
        assert len(ret) > 0
        # 0xAA in 32 bytes big-endian
        assert ret.endswith("aa")

    def test_revert_opcode(self):
        prog = _bytes(
            Opcode.PUSH1, 0,   # length
            Opcode.PUSH1, 0,   # offset
            Opcode.REVERT,
        )
        d = _make_debugger()
        d.load_bytecode(prog)
        d.continue_execution()
        assert d.is_halted()


# ═══════════════════════════════════════════════════════════════════════
#  Test: Stack Underflow
# ═══════════════════════════════════════════════════════════════════════

class TestStackErrors:
    """Tests for stack underflow conditions."""

    def test_add_underflow(self):
        d = _make_debugger()
        d.load_bytecode(_bytes(Opcode.PUSH1, 1, Opcode.ADD))
        d.step()  # PUSH1
        result = d.step()  # ADD with only 1 item
        assert result["halted"] is True

    def test_pop_underflow(self):
        d = _make_debugger()
        d.load_bytecode(_bytes(Opcode.POP))
        result = d.step()
        assert result["halted"] is True

    def test_dup_underflow(self):
        d = _make_debugger()
        d.load_bytecode(_bytes(Opcode.DUP1))
        result = d.step()
        assert result["halted"] is True


# ═══════════════════════════════════════════════════════════════════════
#  Test: Statistics & State
# ═══════════════════════════════════════════════════════════════════════

class TestStatsAndState:
    """Tests for debugger stats and state queries."""

    def test_get_stats(self):
        d = _make_debugger()
        d.load_bytecode(SIMPLE_ADD)
        d.continue_execution()
        stats = d.get_stats()
        assert stats["bytecode_size"] == len(SIMPLE_ADD)
        assert stats["halted"] is True
        assert stats["step_count"] > 0
        assert stats["gas_used"] > 0

    def test_get_stack_hex(self):
        d = _make_debugger()
        d.load_bytecode(SIMPLE_ADD)
        d.step()  # PUSH1 5
        stack = d.get_stack()
        assert stack == ["0x5"]

    def test_get_storage_dict(self):
        d = _make_debugger()
        d.load_bytecode(STORAGE_PROG)
        d.continue_execution()
        storage = d.get_storage()
        assert isinstance(storage, dict)
        assert len(storage) == 1

    def test_get_return_data_empty(self):
        d = _make_debugger()
        d.load_bytecode(SIMPLE_ADD)
        d.continue_execution()
        assert d.get_return_data() == ""

    def test_is_halted_false(self):
        d = _make_debugger()
        d.load_bytecode(SIMPLE_ADD)
        assert not d.is_halted()

    def test_is_halted_true(self):
        d = _make_debugger()
        d.load_bytecode(_bytes(Opcode.STOP))
        d.step()
        assert d.is_halted()

    def test_execution_step_to_dict(self):
        d = _make_debugger()
        d.load_bytecode(SIMPLE_ADD)
        d.step()
        trace = d.get_trace()
        step = trace[0]
        assert step["step"] == 1
        assert "opcode" in step
        assert "gas_cost" in step

    def test_end_of_bytecode_halts(self):
        d = _make_debugger()
        d.load_bytecode(_bytes(Opcode.JUMPDEST))
        d.step()  # JUMPDEST
        result = d.step()  # Past end of bytecode
        assert result["halted"] is True
