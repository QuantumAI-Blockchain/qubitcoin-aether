"""Tests for QVM quantum opcode extensions (QCREATE, QVERIFY, QCOMPLIANCE, QRISK)."""
import pytest


class TestOpcodeDefinitions:
    """Verify opcode enum values and gas costs."""

    def test_qcreate_at_0xda(self):
        from qubitcoin.qvm.opcodes import Opcode
        assert Opcode.QCREATE == 0xDA

    def test_qverify_at_0xdb(self):
        from qubitcoin.qvm.opcodes import Opcode
        assert Opcode.QVERIFY == 0xDB

    def test_qcompliance_at_0xdc(self):
        from qubitcoin.qvm.opcodes import Opcode
        assert Opcode.QCOMPLIANCE == 0xDC

    def test_qrisk_at_0xdd(self):
        from qubitcoin.qvm.opcodes import Opcode
        assert Opcode.QRISK == 0xDD

    def test_qrisk_systemic_at_0xde(self):
        from qubitcoin.qvm.opcodes import Opcode
        assert Opcode.QRISK_SYSTEMIC == 0xDE

    def test_qcreate_gas_cost(self):
        from qubitcoin.qvm.opcodes import GAS_COSTS, Opcode
        assert GAS_COSTS[Opcode.QCREATE] == 5000

    def test_qverify_gas_cost(self):
        from qubitcoin.qvm.opcodes import GAS_COSTS, Opcode
        assert GAS_COSTS[Opcode.QVERIFY] == 8000

    def test_qcompliance_gas_cost(self):
        from qubitcoin.qvm.opcodes import GAS_COSTS, Opcode
        assert GAS_COSTS[Opcode.QCOMPLIANCE] == 15000

    def test_qrisk_gas_cost(self):
        from qubitcoin.qvm.opcodes import GAS_COSTS, Opcode
        assert GAS_COSTS[Opcode.QRISK] == 5000

    def test_qrisk_systemic_gas_cost(self):
        from qubitcoin.qvm.opcodes import GAS_COSTS, Opcode
        assert GAS_COSTS[Opcode.QRISK_SYSTEMIC] == 10000

    def test_qcreate_in_quantum_set(self):
        from qubitcoin.qvm.opcodes import QUANTUM_OPCODES, Opcode
        assert Opcode.QCREATE in QUANTUM_OPCODES

    def test_qcreate_exponential_gas(self):
        from qubitcoin.qvm.opcodes import get_quantum_gas_cost, Opcode
        gas_1q = get_quantum_gas_cost(Opcode.QCREATE, n_qubits=1)
        gas_4q = get_quantum_gas_cost(Opcode.QCREATE, n_qubits=4)
        assert gas_4q > gas_1q
        assert gas_1q == 5000 + 5000 * 2
        assert gas_4q == 5000 + 5000 * 16


class TestCanonicalMapping:
    """Verify the whitepaper canonical opcode mapping table."""

    def test_canonical_map_exists(self):
        from qubitcoin.qvm.opcodes import CANONICAL_OPCODE_MAP
        assert isinstance(CANONICAL_OPCODE_MAP, dict)

    def test_canonical_map_has_10_entries(self):
        from qubitcoin.qvm.opcodes import CANONICAL_OPCODE_MAP
        assert len(CANONICAL_OPCODE_MAP) == 10

    def test_canonical_f0_is_qcreate(self):
        from qubitcoin.qvm.opcodes import CANONICAL_OPCODE_MAP, Opcode
        assert CANONICAL_OPCODE_MAP[0xF0] == Opcode.QCREATE

    def test_canonical_f1_is_qmeasure(self):
        from qubitcoin.qvm.opcodes import CANONICAL_OPCODE_MAP, Opcode
        assert CANONICAL_OPCODE_MAP[0xF1] == Opcode.QMEASURE

    def test_canonical_f2_is_qentangle(self):
        from qubitcoin.qvm.opcodes import CANONICAL_OPCODE_MAP, Opcode
        assert CANONICAL_OPCODE_MAP[0xF2] == Opcode.QENTANGLE

    def test_canonical_f3_is_qgate(self):
        from qubitcoin.qvm.opcodes import CANONICAL_OPCODE_MAP, Opcode
        assert CANONICAL_OPCODE_MAP[0xF3] == Opcode.QGATE

    def test_canonical_f4_is_qverify(self):
        from qubitcoin.qvm.opcodes import CANONICAL_OPCODE_MAP, Opcode
        assert CANONICAL_OPCODE_MAP[0xF4] == Opcode.QVERIFY

    def test_canonical_f5_is_qcompliance(self):
        from qubitcoin.qvm.opcodes import CANONICAL_OPCODE_MAP, Opcode
        assert CANONICAL_OPCODE_MAP[0xF5] == Opcode.QCOMPLIANCE

    def test_canonical_f6_is_qrisk(self):
        from qubitcoin.qvm.opcodes import CANONICAL_OPCODE_MAP, Opcode
        assert CANONICAL_OPCODE_MAP[0xF6] == Opcode.QRISK

    def test_canonical_f7_is_qrisk_systemic(self):
        from qubitcoin.qvm.opcodes import CANONICAL_OPCODE_MAP, Opcode
        assert CANONICAL_OPCODE_MAP[0xF7] == Opcode.QRISK_SYSTEMIC


def _make_vm():
    from qubitcoin.qvm.vm import QVM
    from unittest.mock import MagicMock
    return QVM(quantum_engine=MagicMock())


def _run(vm, bytecode: bytes, gas: int = 1_000_000):
    return vm.execute('0x' + 'aa' * 20, '0x' + 'bb' * 20, bytecode, b'', 0, gas)


class TestQCreateExecution:
    """Test QCREATE opcode execution in the QVM."""

    def test_qcreate_returns_state_id(self):
        from qubitcoin.qvm.opcodes import Opcode
        vm = _make_vm()
        bytecode = bytes([
            Opcode.PUSH1, 4, Opcode.QCREATE,
            Opcode.PUSH1, 0, Opcode.MSTORE,
            Opcode.PUSH1, 32, Opcode.PUSH1, 0, Opcode.RETURN,
        ])
        result = _run(vm, bytecode)
        assert result.success is True
        assert len(result.return_data) == 32
        state_id = int.from_bytes(result.return_data, 'big')
        assert state_id != 0

    def test_qcreate_deterministic(self):
        from qubitcoin.qvm.opcodes import Opcode
        vm = _make_vm()
        bytecode = bytes([
            Opcode.PUSH1, 2, Opcode.QCREATE,
            Opcode.PUSH1, 0, Opcode.MSTORE,
            Opcode.PUSH1, 32, Opcode.PUSH1, 0, Opcode.RETURN,
        ])
        r1 = _run(vm, bytecode)
        r2 = _run(vm, bytecode)
        assert r1.return_data == r2.return_data

    def test_qcreate_different_qubits_different_state(self):
        from qubitcoin.qvm.opcodes import Opcode
        vm = _make_vm()

        def run_n(n):
            bc = bytes([
                Opcode.PUSH1, n, Opcode.QCREATE,
                Opcode.PUSH1, 0, Opcode.MSTORE,
                Opcode.PUSH1, 32, Opcode.PUSH1, 0, Opcode.RETURN,
            ])
            return _run(vm, bc).return_data

        assert run_n(2) != run_n(4)


class TestQVerifyExecution:
    def test_qverify_registered_proof(self):
        """A proof registered in _registered_proofs should verify successfully."""
        from qubitcoin.qvm.opcodes import Opcode
        vm = _make_vm()
        vm._registered_proofs = {99}  # Register proof_hash=99
        bytecode = bytes([
            Opcode.PUSH1, 42, Opcode.PUSH1, 99, Opcode.QVERIFY,
            Opcode.PUSH1, 0, Opcode.MSTORE,
            Opcode.PUSH1, 32, Opcode.PUSH1, 0, Opcode.RETURN,
        ])
        result = _run(vm, bytecode)
        assert result.success is True
        assert int.from_bytes(result.return_data, 'big') == 1

    def test_qverify_unregistered_proof(self):
        """An unregistered non-zero proof should fail verification."""
        from qubitcoin.qvm.opcodes import Opcode
        vm = _make_vm()
        bytecode = bytes([
            Opcode.PUSH1, 42, Opcode.PUSH1, 99, Opcode.QVERIFY,
            Opcode.PUSH1, 0, Opcode.MSTORE,
            Opcode.PUSH1, 32, Opcode.PUSH1, 0, Opcode.RETURN,
        ])
        result = _run(vm, bytecode)
        assert result.success is True
        assert int.from_bytes(result.return_data, 'big') == 0

    def test_qverify_zero_proof_fails(self):
        from qubitcoin.qvm.opcodes import Opcode
        vm = _make_vm()
        bytecode = bytes([
            Opcode.PUSH1, 42, Opcode.PUSH1, 0, Opcode.QVERIFY,
            Opcode.PUSH1, 0, Opcode.MSTORE,
            Opcode.PUSH1, 32, Opcode.PUSH1, 0, Opcode.RETURN,
        ])
        result = _run(vm, bytecode)
        assert result.success is True
        assert int.from_bytes(result.return_data, 'big') == 0


class TestQComplianceExecution:
    def test_qcompliance_returns_level_1(self):
        from qubitcoin.qvm.opcodes import Opcode
        vm = _make_vm()
        bytecode = bytes([
            Opcode.PUSH1, 0x55, Opcode.QCOMPLIANCE,
            Opcode.PUSH1, 0, Opcode.MSTORE,
            Opcode.PUSH1, 32, Opcode.PUSH1, 0, Opcode.RETURN,
        ])
        result = _run(vm, bytecode)
        assert result.success is True
        assert int.from_bytes(result.return_data, 'big') == 1


class TestQRiskExecution:
    def test_qrisk_returns_score(self):
        from qubitcoin.qvm.opcodes import Opcode
        vm = _make_vm()
        bytecode = bytes([
            Opcode.PUSH1, 0xAA, Opcode.QRISK,
            Opcode.PUSH1, 0, Opcode.MSTORE,
            Opcode.PUSH1, 32, Opcode.PUSH1, 0, Opcode.RETURN,
        ])
        result = _run(vm, bytecode)
        assert result.success is True
        assert int.from_bytes(result.return_data, 'big') == 10 * 10**16

    def test_qrisk_systemic(self):
        from qubitcoin.qvm.opcodes import Opcode
        vm = _make_vm()
        bytecode = bytes([
            Opcode.QRISK_SYSTEMIC,
            Opcode.PUSH1, 0, Opcode.MSTORE,
            Opcode.PUSH1, 32, Opcode.PUSH1, 0, Opcode.RETURN,
        ])
        result = _run(vm, bytecode)
        assert result.success is True
        assert int.from_bytes(result.return_data, 'big') == 5 * 10**16


class TestAllQuantumOpcodesHaveGas:
    def test_all_quantum_opcodes_in_gas_table(self):
        from qubitcoin.qvm.opcodes import Opcode, GAS_COSTS
        quantum_ops = [
            Opcode.QGATE, Opcode.QMEASURE, Opcode.QENTANGLE,
            Opcode.QSUPERPOSE, Opcode.QVQE, Opcode.QHAMILTONIAN,
            Opcode.QENERGY, Opcode.QPROOF, Opcode.QFIDELITY,
            Opcode.QDILITHIUM, Opcode.QCREATE, Opcode.QVERIFY,
            Opcode.QCOMPLIANCE, Opcode.QRISK, Opcode.QRISK_SYSTEMIC,
        ]
        for op in quantum_ops:
            assert op in GAS_COSTS, f"{op.name} (0x{op:02x}) missing from GAS_COSTS"
            assert GAS_COSTS[op] > 0, f"{op.name} has zero gas cost"
