"""Tests for QBRIDGE_ENTANGLE and QBRIDGE_VERIFY opcodes (Batch 12.2)."""
import pytest
from unittest.mock import MagicMock

from qubitcoin.qvm.opcodes import (
    Opcode, GAS_COSTS, CANONICAL_OPCODE_MAP, get_quantum_gas_cost,
)
from qubitcoin.qvm.vm import QVM, ExecutionResult


def _make_vm() -> QVM:
    return QVM(quantum_engine=MagicMock())


def _run(vm: QVM, bytecode: bytes, gas: int = 1_000_000) -> ExecutionResult:
    return vm.execute('0x' + 'aa' * 20, '0x' + 'bb' * 20, bytecode, b'', 0, gas)


class TestBridgeOpcodeDefinitions:
    """Verify enum values, gas costs, and canonical mapping."""

    def test_qbridge_entangle_value(self):
        assert Opcode.QBRIDGE_ENTANGLE == 0xC0

    def test_qbridge_verify_value(self):
        assert Opcode.QBRIDGE_VERIFY == 0xC1

    def test_qbridge_entangle_gas(self):
        assert GAS_COSTS[Opcode.QBRIDGE_ENTANGLE] == 20000

    def test_qbridge_verify_gas(self):
        assert GAS_COSTS[Opcode.QBRIDGE_VERIFY] == 15000

    def test_canonical_f8_maps_to_bridge_entangle(self):
        assert CANONICAL_OPCODE_MAP[0xF8] == Opcode.QBRIDGE_ENTANGLE

    def test_canonical_f9_maps_to_bridge_verify(self):
        assert CANONICAL_OPCODE_MAP[0xF9] == Opcode.QBRIDGE_VERIFY

    def test_canonical_map_now_has_10_entries(self):
        assert len(CANONICAL_OPCODE_MAP) == 10


class TestQBridgeEntangleExecution:
    """Test QBRIDGE_ENTANGLE opcode VM execution."""

    def test_returns_entanglement_id(self):
        vm = _make_vm()
        bc = bytes([
            Opcode.PUSH1, 0x01,  # state_hash
            Opcode.PUSH1, 0x02,  # dest_chain_id
            Opcode.PUSH1, 0x03,  # source_chain_id
            Opcode.QBRIDGE_ENTANGLE,
            Opcode.PUSH1, 0,
            Opcode.MSTORE,
            Opcode.PUSH1, 32, Opcode.PUSH1, 0, Opcode.RETURN,
        ])
        result = _run(vm, bc)
        assert result.success is True
        ent_id = int.from_bytes(result.return_data, 'big')
        assert ent_id != 0

    def test_deterministic_entanglement_id(self):
        vm = _make_vm()
        bc = bytes([
            Opcode.PUSH1, 0x10,
            Opcode.PUSH1, 0x20,
            Opcode.PUSH1, 0x30,
            Opcode.QBRIDGE_ENTANGLE,
            Opcode.PUSH1, 0,
            Opcode.MSTORE,
            Opcode.PUSH1, 32, Opcode.PUSH1, 0, Opcode.RETURN,
        ])
        r1 = _run(vm, bc)
        r2 = _run(vm, bc)
        assert r1.return_data == r2.return_data

    def test_different_chains_different_id(self):
        vm = _make_vm()

        def run_with_chains(src: int, dst: int) -> bytes:
            bc = bytes([
                Opcode.PUSH1, 0x01,
                Opcode.PUSH1, dst,
                Opcode.PUSH1, src,
                Opcode.QBRIDGE_ENTANGLE,
                Opcode.PUSH1, 0,
                Opcode.MSTORE,
                Opcode.PUSH1, 32, Opcode.PUSH1, 0, Opcode.RETURN,
            ])
            return _run(vm, bc).return_data

        assert run_with_chains(1, 2) != run_with_chains(3, 4)


class TestQBridgeVerifyExecution:
    """Test QBRIDGE_VERIFY opcode VM execution."""

    def test_valid_proof_returns_1(self):
        vm = _make_vm()
        bc = bytes([
            Opcode.PUSH1, 0x01,  # source_chain_id (non-zero)
            Opcode.PUSH1, 0xFF,  # proof_hash (non-zero)
            Opcode.QBRIDGE_VERIFY,
            Opcode.PUSH1, 0,
            Opcode.MSTORE,
            Opcode.PUSH1, 32, Opcode.PUSH1, 0, Opcode.RETURN,
        ])
        result = _run(vm, bc)
        assert result.success is True
        assert int.from_bytes(result.return_data, 'big') == 1

    def test_zero_proof_returns_0(self):
        vm = _make_vm()
        bc = bytes([
            Opcode.PUSH1, 0x01,  # source_chain_id
            Opcode.PUSH1, 0x00,  # proof_hash = 0
            Opcode.QBRIDGE_VERIFY,
            Opcode.PUSH1, 0,
            Opcode.MSTORE,
            Opcode.PUSH1, 32, Opcode.PUSH1, 0, Opcode.RETURN,
        ])
        result = _run(vm, bc)
        assert int.from_bytes(result.return_data, 'big') == 0

    def test_zero_chain_returns_0(self):
        vm = _make_vm()
        bc = bytes([
            Opcode.PUSH1, 0x00,  # source_chain_id = 0
            Opcode.PUSH1, 0xFF,  # proof_hash
            Opcode.QBRIDGE_VERIFY,
            Opcode.PUSH1, 0,
            Opcode.MSTORE,
            Opcode.PUSH1, 32, Opcode.PUSH1, 0, Opcode.RETURN,
        ])
        result = _run(vm, bc)
        assert int.from_bytes(result.return_data, 'big') == 0


class TestBridgeOpcodeGas:
    """Verify gas consumption for bridge opcodes."""

    def test_bridge_entangle_consumes_gas(self):
        vm = _make_vm()
        bc = bytes([
            Opcode.PUSH1, 1, Opcode.PUSH1, 2, Opcode.PUSH1, 3,
            Opcode.QBRIDGE_ENTANGLE, Opcode.POP, Opcode.STOP,
        ])
        result = _run(vm, bc, gas=100_000)
        assert result.success is True
        assert result.gas_used >= 20000  # At least the opcode cost

    def test_bridge_verify_consumes_gas(self):
        vm = _make_vm()
        bc = bytes([
            Opcode.PUSH1, 1, Opcode.PUSH1, 0xFF,
            Opcode.QBRIDGE_VERIFY, Opcode.POP, Opcode.STOP,
        ])
        result = _run(vm, bc, gas=100_000)
        assert result.success is True
        assert result.gas_used >= 15000
