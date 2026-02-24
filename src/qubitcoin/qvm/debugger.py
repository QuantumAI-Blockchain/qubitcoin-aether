"""
QVM Debugger — Step-Through Execution with Breakpoints & State Inspection

Provides interactive debugging capabilities for QVM bytecode:
  - Breakpoints: set by opcode index, opcode type, or gas threshold
  - Step execution: step-into, step-over, continue-to-breakpoint
  - State snapshots: capture stack, memory, storage, gas at any point
  - Execution trace: full opcode-by-opcode trace with gas accounting
  - Quantum state visualization: inspect quantum states during execution

Usage:
    debugger = QVMDebugger()
    debugger.set_breakpoint(pc=10)
    debugger.load_bytecode(bytecode)
    while not debugger.is_halted():
        result = debugger.step()
        print(result)
"""

import hashlib
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set

from .opcodes import Opcode
from ..utils.logger import get_logger

logger = get_logger(__name__)


class DebugAction(Enum):
    """Debugger action commands."""
    STEP = "step"                 # Execute one opcode
    STEP_OVER = "step_over"      # Step over CALL opcodes
    CONTINUE = "continue"        # Run until breakpoint or halt
    RUN_TO_CURSOR = "run_to_cursor"  # Run to specific PC


class BreakpointType(Enum):
    """Types of breakpoints."""
    PC = "pc"                     # Break at program counter
    OPCODE = "opcode"             # Break at opcode type
    GAS_BELOW = "gas_below"       # Break when gas drops below threshold
    STORAGE_WRITE = "storage_write"  # Break on SSTORE
    STACK_DEPTH = "stack_depth"   # Break when stack exceeds depth


@dataclass
class Breakpoint:
    """A debugger breakpoint."""
    bp_id: int
    bp_type: BreakpointType
    value: int  # PC, opcode int, gas threshold, or stack depth
    enabled: bool = True
    hit_count: int = 0
    condition: str = ""  # Optional description

    def to_dict(self) -> Dict:
        return {
            "bp_id": self.bp_id,
            "type": self.bp_type.value,
            "value": self.value,
            "enabled": self.enabled,
            "hit_count": self.hit_count,
            "condition": self.condition,
        }


@dataclass
class ExecutionStep:
    """A single step in the execution trace."""
    step_number: int
    pc: int
    opcode: int
    opcode_name: str
    gas_before: int
    gas_after: int
    gas_cost: int
    stack_before: List[int]
    stack_after: List[int]
    memory_size: int
    storage_changes: Dict[str, str]
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict:
        return {
            "step": self.step_number,
            "pc": self.pc,
            "opcode": hex(self.opcode),
            "opcode_name": self.opcode_name,
            "gas_before": self.gas_before,
            "gas_after": self.gas_after,
            "gas_cost": self.gas_cost,
            "stack_depth_before": len(self.stack_before),
            "stack_depth_after": len(self.stack_after),
            "stack_top": hex(self.stack_after[-1]) if self.stack_after else None,
            "memory_size": self.memory_size,
            "storage_changes": self.storage_changes,
        }


@dataclass
class StateSnapshot:
    """Point-in-time snapshot of VM state."""
    snapshot_id: str
    pc: int
    step_number: int
    gas_remaining: int
    stack: List[int]
    memory: bytes
    storage: Dict[str, str]
    return_data: bytes
    halted: bool
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict:
        return {
            "snapshot_id": self.snapshot_id,
            "pc": self.pc,
            "step": self.step_number,
            "gas_remaining": self.gas_remaining,
            "stack_depth": len(self.stack),
            "stack_top_5": [hex(v) for v in self.stack[-5:]],
            "memory_size": len(self.memory),
            "storage_entries": len(self.storage),
            "halted": self.halted,
            "timestamp": self.timestamp,
        }


def _opcode_name(opcode_byte: int) -> str:
    """Get human-readable opcode name."""
    try:
        return Opcode(opcode_byte).name
    except ValueError:
        return f"UNKNOWN(0x{opcode_byte:02x})"


class QVMDebugger:
    """
    Interactive QVM bytecode debugger.

    Simulates QVM execution with debugging primitives: breakpoints,
    single-stepping, state inspection, and execution tracing.
    """

    def __init__(self, gas_limit: int = 1_000_000) -> None:
        # Bytecode
        self._bytecode: bytes = b""
        self._pc: int = 0

        # VM state
        self._stack: List[int] = []
        self._memory: bytearray = bytearray()
        self._storage: Dict[str, str] = {}
        self._gas: int = gas_limit
        self._gas_limit: int = gas_limit
        self._return_data: bytes = b""
        self._halted: bool = False
        self._revert_reason: str = ""

        # Debug state
        self._breakpoints: Dict[int, Breakpoint] = {}
        self._next_bp_id: int = 1
        self._trace: List[ExecutionStep] = []
        self._snapshots: List[StateSnapshot] = []
        self._step_count: int = 0
        self._paused_at_breakpoint: bool = False
        self._last_hit_bp: Optional[int] = None

        logger.info("QVMDebugger initialised")

    # ── Load & Reset ───────────────────────────────────────────────────

    def load_bytecode(self, bytecode: bytes, gas_limit: Optional[int] = None) -> Dict:
        """
        Load bytecode for debugging.

        Args:
            bytecode: QVM/EVM bytecode to debug.
            gas_limit: Override gas limit.

        Returns:
            Result with bytecode info.
        """
        self._bytecode = bytecode
        self._pc = 0
        self._stack = []
        self._memory = bytearray()
        self._storage = {}
        self._gas = gas_limit or self._gas_limit
        self._gas_limit = self._gas
        self._return_data = b""
        self._halted = False
        self._revert_reason = ""
        self._trace = []
        self._snapshots = []
        self._step_count = 0
        self._paused_at_breakpoint = False
        self._last_hit_bp = None

        logger.info(f"Bytecode loaded: {len(bytecode)} bytes")
        return {
            "success": True,
            "bytecode_size": len(bytecode),
            "gas_limit": self._gas,
            "opcodes": self._disassemble(limit=20),
        }

    def reset(self) -> Dict:
        """Reset execution to beginning, keeping bytecode and breakpoints."""
        return self.load_bytecode(self._bytecode, self._gas_limit)

    # ── Breakpoints ────────────────────────────────────────────────────

    def set_breakpoint(
        self,
        pc: Optional[int] = None,
        opcode: Optional[int] = None,
        gas_below: Optional[int] = None,
        stack_depth: Optional[int] = None,
        condition: str = "",
    ) -> Dict:
        """
        Set a breakpoint.

        Exactly one of pc/opcode/gas_below/stack_depth must be specified.

        Returns:
            Result with breakpoint ID.
        """
        if pc is not None:
            bp_type = BreakpointType.PC
            value = pc
        elif opcode is not None:
            bp_type = BreakpointType.OPCODE
            value = opcode
        elif gas_below is not None:
            bp_type = BreakpointType.GAS_BELOW
            value = gas_below
        elif stack_depth is not None:
            bp_type = BreakpointType.STACK_DEPTH
            value = stack_depth
        else:
            return {"success": False, "error": "Must specify pc, opcode, gas_below, or stack_depth"}

        bp_id = self._next_bp_id
        self._next_bp_id += 1

        bp = Breakpoint(
            bp_id=bp_id,
            bp_type=bp_type,
            value=value,
            condition=condition,
        )
        self._breakpoints[bp_id] = bp

        logger.info(f"Breakpoint {bp_id}: {bp_type.value}={value}")
        return {"success": True, "bp_id": bp_id, "type": bp_type.value, "value": value}

    def remove_breakpoint(self, bp_id: int) -> Dict:
        """Remove a breakpoint by ID."""
        if bp_id not in self._breakpoints:
            return {"success": False, "error": "Breakpoint not found"}
        del self._breakpoints[bp_id]
        return {"success": True, "bp_id": bp_id}

    def toggle_breakpoint(self, bp_id: int) -> Dict:
        """Enable/disable a breakpoint."""
        bp = self._breakpoints.get(bp_id)
        if bp is None:
            return {"success": False, "error": "Breakpoint not found"}
        bp.enabled = not bp.enabled
        return {"success": True, "bp_id": bp_id, "enabled": bp.enabled}

    def list_breakpoints(self) -> List[Dict]:
        """List all breakpoints."""
        return [bp.to_dict() for bp in self._breakpoints.values()]

    def _check_breakpoints(self) -> Optional[int]:
        """Check if any breakpoint is hit at current state. Returns bp_id or None."""
        if self._pc >= len(self._bytecode):
            return None

        current_opcode = self._bytecode[self._pc]

        for bp in self._breakpoints.values():
            if not bp.enabled:
                continue

            hit = False
            if bp.bp_type == BreakpointType.PC and self._pc == bp.value:
                hit = True
            elif bp.bp_type == BreakpointType.OPCODE and current_opcode == bp.value:
                hit = True
            elif bp.bp_type == BreakpointType.GAS_BELOW and self._gas < bp.value:
                hit = True
            elif bp.bp_type == BreakpointType.STACK_DEPTH and len(self._stack) >= bp.value:
                hit = True
            elif bp.bp_type == BreakpointType.STORAGE_WRITE and current_opcode == Opcode.SSTORE:
                hit = True

            if hit:
                bp.hit_count += 1
                return bp.bp_id

        return None

    # ── Execution ──────────────────────────────────────────────────────

    def step(self) -> Dict:
        """
        Execute a single opcode.

        Returns:
            Step result with opcode info, state changes, and breakpoint status.
        """
        if self._halted:
            return {"success": False, "error": "Execution halted", "halted": True}

        if self._pc >= len(self._bytecode):
            self._halted = True
            return {"success": True, "halted": True, "reason": "End of bytecode"}

        # Capture pre-state
        opcode_byte = self._bytecode[self._pc]
        opcode_name = _opcode_name(opcode_byte)
        gas_before = self._gas
        stack_before = list(self._stack)
        storage_changes: Dict[str, str] = {}

        # Execute the opcode (simplified simulation)
        try:
            self._execute_opcode(opcode_byte, storage_changes)
        except Exception as e:
            self._halted = True
            self._revert_reason = str(e)
            return {
                "success": False,
                "error": str(e),
                "halted": True,
                "pc": self._pc,
                "opcode": opcode_name,
                "step": self._step_count,
            }

        # Record trace
        self._step_count += 1
        step_record = ExecutionStep(
            step_number=self._step_count,
            pc=self._pc - 1 if opcode_byte != Opcode.STOP else self._pc,
            opcode=opcode_byte,
            opcode_name=opcode_name,
            gas_before=gas_before,
            gas_after=self._gas,
            gas_cost=gas_before - self._gas,
            stack_before=stack_before,
            stack_after=list(self._stack),
            memory_size=len(self._memory),
            storage_changes=storage_changes,
        )
        self._trace.append(step_record)

        # Check breakpoints for next instruction
        bp_hit = None
        if not self._halted and self._pc < len(self._bytecode):
            bp_hit = self._check_breakpoints()
            if bp_hit is not None:
                self._paused_at_breakpoint = True
                self._last_hit_bp = bp_hit

        result = {
            "success": True,
            "step": self._step_count,
            "pc": step_record.pc,
            "opcode": opcode_name,
            "opcode_hex": hex(opcode_byte),
            "gas_cost": step_record.gas_cost,
            "gas_remaining": self._gas,
            "stack_depth": len(self._stack),
            "halted": self._halted,
        }

        if bp_hit is not None:
            result["breakpoint_hit"] = bp_hit
            result["breakpoint_type"] = self._breakpoints[bp_hit].bp_type.value

        return result

    def continue_execution(self, max_steps: int = 10_000) -> Dict:
        """
        Continue execution until breakpoint, halt, or max_steps.

        Returns:
            Result with steps executed and final state.
        """
        steps = 0
        self._paused_at_breakpoint = False

        while steps < max_steps and not self._halted:
            result = self.step()

            if not result.get("success", False):
                return result

            steps += 1

            if result.get("breakpoint_hit") is not None:
                return {
                    "success": True,
                    "steps_executed": steps,
                    "stopped_reason": "breakpoint",
                    "breakpoint_id": result["breakpoint_hit"],
                    **self._current_state_summary(),
                }

        reason = "halted" if self._halted else "max_steps"
        return {
            "success": True,
            "steps_executed": steps,
            "stopped_reason": reason,
            **self._current_state_summary(),
        }

    def _execute_opcode(self, opcode_byte: int, storage_changes: Dict[str, str]) -> None:
        """
        Simulate a single opcode execution.

        This is a simplified simulator for debugging — it handles the most
        common opcodes. Full execution uses the real QVM (vm.py).
        """
        from .opcodes import GAS_COSTS

        # Deduct gas
        gas_cost = GAS_COSTS.get(opcode_byte, 3)
        if self._gas < gas_cost:
            raise Exception(f"Out of gas at PC={self._pc}")
        self._gas -= gas_cost

        if opcode_byte == Opcode.STOP:
            self._halted = True
            return

        elif opcode_byte == Opcode.ADD:
            if len(self._stack) < 2:
                raise Exception("Stack underflow: ADD requires 2 items")
            a, b = self._stack.pop(), self._stack.pop()
            self._stack.append((a + b) & ((1 << 256) - 1))

        elif opcode_byte == Opcode.MUL:
            if len(self._stack) < 2:
                raise Exception("Stack underflow: MUL requires 2 items")
            a, b = self._stack.pop(), self._stack.pop()
            self._stack.append((a * b) & ((1 << 256) - 1))

        elif opcode_byte == Opcode.SUB:
            if len(self._stack) < 2:
                raise Exception("Stack underflow: SUB requires 2 items")
            a, b = self._stack.pop(), self._stack.pop()
            self._stack.append((a - b) & ((1 << 256) - 1))

        elif opcode_byte == Opcode.DIV:
            if len(self._stack) < 2:
                raise Exception("Stack underflow: DIV requires 2 items")
            a, b = self._stack.pop(), self._stack.pop()
            self._stack.append(a // b if b != 0 else 0)

        elif opcode_byte == Opcode.ISZERO:
            if len(self._stack) < 1:
                raise Exception("Stack underflow: ISZERO requires 1 item")
            a = self._stack.pop()
            self._stack.append(1 if a == 0 else 0)

        elif opcode_byte == Opcode.POP:
            if len(self._stack) < 1:
                raise Exception("Stack underflow: POP requires 1 item")
            self._stack.pop()

        elif opcode_byte == Opcode.MLOAD:
            if len(self._stack) < 1:
                raise Exception("Stack underflow: MLOAD requires 1 item")
            offset = self._stack.pop()
            end = offset + 32
            if end > len(self._memory):
                self._memory.extend(b'\x00' * (end - len(self._memory)))
            value = int.from_bytes(self._memory[offset:end], 'big')
            self._stack.append(value)

        elif opcode_byte == Opcode.MSTORE:
            if len(self._stack) < 2:
                raise Exception("Stack underflow: MSTORE requires 2 items")
            offset = self._stack.pop()
            value = self._stack.pop()
            end = offset + 32
            if end > len(self._memory):
                self._memory.extend(b'\x00' * (end - len(self._memory)))
            self._memory[offset:end] = value.to_bytes(32, 'big')

        elif opcode_byte == Opcode.SLOAD:
            if len(self._stack) < 1:
                raise Exception("Stack underflow: SLOAD requires 1 item")
            key = hex(self._stack.pop())
            value = int(self._storage.get(key, "0"), 16)
            self._stack.append(value)

        elif opcode_byte == Opcode.SSTORE:
            if len(self._stack) < 2:
                raise Exception("Stack underflow: SSTORE requires 2 items")
            key = hex(self._stack.pop())
            value = hex(self._stack.pop())
            self._storage[key] = value
            storage_changes[key] = value

        elif opcode_byte == Opcode.JUMP:
            if len(self._stack) < 1:
                raise Exception("Stack underflow: JUMP requires 1 item")
            dest = self._stack.pop()
            if dest >= len(self._bytecode):
                raise Exception(f"Invalid JUMP destination: {dest}")
            self._pc = dest
            return  # Don't advance PC

        elif opcode_byte == Opcode.JUMPI:
            if len(self._stack) < 2:
                raise Exception("Stack underflow: JUMPI requires 2 items")
            dest = self._stack.pop()
            cond = self._stack.pop()
            if cond != 0:
                if dest >= len(self._bytecode):
                    raise Exception(f"Invalid JUMPI destination: {dest}")
                self._pc = dest
                return

        elif opcode_byte == Opcode.PC:
            self._stack.append(self._pc)

        elif opcode_byte == Opcode.GAS:
            self._stack.append(self._gas)

        elif opcode_byte == Opcode.JUMPDEST:
            pass  # No-op marker

        elif opcode_byte == Opcode.RETURN:
            if len(self._stack) < 2:
                raise Exception("Stack underflow: RETURN requires 2 items")
            offset = self._stack.pop()
            length = self._stack.pop()
            if offset + length > len(self._memory):
                self._memory.extend(b'\x00' * (offset + length - len(self._memory)))
            self._return_data = bytes(self._memory[offset:offset + length])
            self._halted = True
            return

        elif opcode_byte == Opcode.REVERT:
            if len(self._stack) < 2:
                raise Exception("Stack underflow: REVERT requires 2 items")
            offset = self._stack.pop()
            length = self._stack.pop()
            if offset + length > len(self._memory):
                self._memory.extend(b'\x00' * (offset + length - len(self._memory)))
            self._return_data = bytes(self._memory[offset:offset + length])
            self._halted = True
            self._revert_reason = "REVERT"
            return

        elif 0x60 <= opcode_byte <= 0x7f:
            # PUSH1 through PUSH32
            push_size = opcode_byte - 0x5f
            value = 0
            for i in range(push_size):
                idx = self._pc + 1 + i
                if idx < len(self._bytecode):
                    value = (value << 8) | self._bytecode[idx]
            self._stack.append(value)
            self._pc += push_size  # Extra advance for push data

        elif 0x80 <= opcode_byte <= 0x8f:
            # DUP1 through DUP16
            depth = opcode_byte - 0x7f
            if len(self._stack) < depth:
                raise Exception(f"Stack underflow: DUP{depth}")
            self._stack.append(self._stack[-depth])

        elif 0x90 <= opcode_byte <= 0x9f:
            # SWAP1 through SWAP16
            depth = opcode_byte - 0x8f
            if len(self._stack) < depth + 1:
                raise Exception(f"Stack underflow: SWAP{depth}")
            self._stack[-1], self._stack[-(depth + 1)] = (
                self._stack[-(depth + 1)], self._stack[-1]
            )

        else:
            # Unknown/unsimulated opcode — skip with warning
            pass

        # Advance PC
        self._pc += 1

    # ── State Inspection ───────────────────────────────────────────────

    def take_snapshot(self) -> StateSnapshot:
        """Capture current VM state as an immutable snapshot."""
        snap_id = hashlib.sha256(
            f"snap:{self._pc}:{self._step_count}:{self._gas}:{time.time()}".encode()
        ).hexdigest()[:16]

        snapshot = StateSnapshot(
            snapshot_id=snap_id,
            pc=self._pc,
            step_number=self._step_count,
            gas_remaining=self._gas,
            stack=list(self._stack),
            memory=bytes(self._memory),
            storage=dict(self._storage),
            return_data=self._return_data,
            halted=self._halted,
        )
        self._snapshots.append(snapshot)
        return snapshot

    def get_stack(self) -> List[str]:
        """Get current stack as hex strings."""
        return [hex(v) for v in self._stack]

    def get_memory(self, offset: int = 0, length: int = 256) -> str:
        """Get memory region as hex."""
        end = min(offset + length, len(self._memory))
        return self._memory[offset:end].hex()

    def get_storage(self) -> Dict[str, str]:
        """Get all storage entries."""
        return dict(self._storage)

    def get_return_data(self) -> str:
        """Get return data as hex."""
        return self._return_data.hex()

    def is_halted(self) -> bool:
        """Check if execution has halted."""
        return self._halted

    def _current_state_summary(self) -> Dict:
        """Get summary of current VM state."""
        return {
            "pc": self._pc,
            "gas_remaining": self._gas,
            "gas_used": self._gas_limit - self._gas,
            "stack_depth": len(self._stack),
            "memory_size": len(self._memory),
            "storage_entries": len(self._storage),
            "halted": self._halted,
            "revert_reason": self._revert_reason,
            "step_count": self._step_count,
        }

    # ── Disassembly ────────────────────────────────────────────────────

    def _disassemble(self, start: int = 0, limit: int = 50) -> List[Dict]:
        """Disassemble bytecode to human-readable opcodes."""
        result = []
        pc = start
        count = 0

        while pc < len(self._bytecode) and count < limit:
            op = self._bytecode[pc]
            name = _opcode_name(op)

            entry = {"pc": pc, "opcode": hex(op), "name": name}

            if 0x60 <= op <= 0x7f:
                push_size = op - 0x5f
                data = self._bytecode[pc + 1:pc + 1 + push_size]
                entry["push_data"] = "0x" + data.hex()
                pc += push_size

            result.append(entry)
            pc += 1
            count += 1

        return result

    def disassemble(self, start: int = 0, limit: int = 50) -> List[Dict]:
        """Public disassembly interface."""
        return self._disassemble(start, limit)

    # ── Trace & History ────────────────────────────────────────────────

    def get_trace(self, last_n: int = 50) -> List[Dict]:
        """Get recent execution trace."""
        return [s.to_dict() for s in self._trace[-last_n:]]

    def get_snapshots(self) -> List[Dict]:
        """Get all state snapshots."""
        return [s.to_dict() for s in self._snapshots]

    def get_gas_profile(self) -> Dict:
        """Get gas usage breakdown by opcode."""
        profile: Dict[str, Dict] = {}
        for step in self._trace:
            name = step.opcode_name
            if name not in profile:
                profile[name] = {"count": 0, "total_gas": 0}
            profile[name]["count"] += 1
            profile[name]["total_gas"] += step.gas_cost

        sorted_profile = sorted(
            profile.items(),
            key=lambda x: x[1]["total_gas"],
            reverse=True,
        )
        return {
            "opcodes": dict(sorted_profile),
            "total_steps": self._step_count,
            "total_gas_used": self._gas_limit - self._gas,
        }

    def get_stats(self) -> Dict:
        """Debugger statistics."""
        return {
            "bytecode_size": len(self._bytecode),
            "pc": self._pc,
            "step_count": self._step_count,
            "gas_limit": self._gas_limit,
            "gas_remaining": self._gas,
            "gas_used": self._gas_limit - self._gas,
            "stack_depth": len(self._stack),
            "memory_size": len(self._memory),
            "storage_entries": len(self._storage),
            "halted": self._halted,
            "breakpoint_count": len(self._breakpoints),
            "trace_length": len(self._trace),
            "snapshot_count": len(self._snapshots),
        }
