"""Tests for compliance registry schema and QCOMPLIANCE handler (Batch 13.3)."""
import os
import pytest
from unittest.mock import MagicMock

from qubitcoin.qvm.opcodes import Opcode, GAS_COSTS
from qubitcoin.qvm.vm import QVM, ExecutionResult


def _make_vm() -> QVM:
    return QVM(quantum_engine=MagicMock())


def _run(vm: QVM, bytecode: bytes, gas: int = 500_000) -> ExecutionResult:
    return vm.execute('0x' + 'aa' * 20, '0x' + 'bb' * 20, bytecode, b'', 0, gas)


class TestComplianceSQLSchema:
    """Verify compliance_registry table in SQL schema."""

    def test_compliance_registry_table_exists(self):
        sql_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'sql')
        sql_path = os.path.join(sql_dir, '03_smart_contracts_qvm.sql')
        with open(sql_path) as f:
            content = f.read()
        assert 'compliance_registry' in content

    def test_compliance_has_kyc_level(self):
        sql_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'sql')
        sql_path = os.path.join(sql_dir, '03_smart_contracts_qvm.sql')
        with open(sql_path) as f:
            content = f.read()
        assert 'kyc_level' in content

    def test_compliance_has_aml_status(self):
        sql_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'sql')
        sql_path = os.path.join(sql_dir, '03_smart_contracts_qvm.sql')
        with open(sql_path) as f:
            content = f.read()
        assert 'aml_status' in content

    def test_compliance_has_sanctions_checked(self):
        sql_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'sql')
        sql_path = os.path.join(sql_dir, '03_smart_contracts_qvm.sql')
        with open(sql_path) as f:
            content = f.read()
        assert 'sanctions_checked' in content

    def test_compliance_has_daily_limit(self):
        sql_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'sql')
        sql_path = os.path.join(sql_dir, '03_smart_contracts_qvm.sql')
        with open(sql_path) as f:
            content = f.read()
        assert 'daily_limit' in content


class TestQComplianceOpcode:
    """Verify QCOMPLIANCE (0xDC) opcode behavior."""

    def test_qcompliance_gas_cost(self):
        assert GAS_COSTS[Opcode.QCOMPLIANCE] == 15000

    def test_qcompliance_returns_basic_level(self):
        vm = _make_vm()
        bc = bytes([
            Opcode.PUSH1, 0xAA,
            Opcode.QCOMPLIANCE,
            Opcode.PUSH1, 0, Opcode.MSTORE,
            Opcode.PUSH1, 32, Opcode.PUSH1, 0, Opcode.RETURN,
        ])
        result = _run(vm, bc)
        assert result.success is True
        assert int.from_bytes(result.return_data, 'big') == 1

    def test_qcompliance_different_addresses_same_default(self):
        """Default compliance returns level 1 regardless of address."""
        vm = _make_vm()
        for addr_byte in [0x01, 0x55, 0xFF]:
            bc = bytes([
                Opcode.PUSH1, addr_byte,
                Opcode.QCOMPLIANCE,
                Opcode.PUSH1, 0, Opcode.MSTORE,
                Opcode.PUSH1, 32, Opcode.PUSH1, 0, Opcode.RETURN,
            ])
            result = _run(vm, bc)
            assert int.from_bytes(result.return_data, 'big') == 1


class TestQRiskOpcode:
    """Verify QRISK returns risk score for addresses."""

    def test_qrisk_gas_cost(self):
        assert GAS_COSTS[Opcode.QRISK] == 5000

    def test_qrisk_returns_low_default(self):
        vm = _make_vm()
        bc = bytes([
            Opcode.PUSH1, 0x42,
            Opcode.QRISK,
            Opcode.PUSH1, 0, Opcode.MSTORE,
            Opcode.PUSH1, 32, Opcode.PUSH1, 0, Opcode.RETURN,
        ])
        result = _run(vm, bc)
        assert result.success is True
        score = int.from_bytes(result.return_data, 'big')
        assert score == 10 * 10**16  # Low risk default

    def test_qrisk_systemic_gas_cost(self):
        assert GAS_COSTS[Opcode.QRISK_SYSTEMIC] == 10000
