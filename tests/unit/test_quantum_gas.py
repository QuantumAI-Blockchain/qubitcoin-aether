"""Unit tests for quantum opcode gas scaling."""
import pytest


class TestQuantumGasScaling:
    """Test exponential gas scaling for quantum opcodes."""

    def test_import(self):
        from qubitcoin.qvm.opcodes import get_quantum_gas_cost, QUANTUM_OPCODES
        assert get_quantum_gas_cost is not None
        assert len(QUANTUM_OPCODES) == 10

    def test_single_qubit_cost(self):
        """1-qubit operation adds 5000 * 2^1 = 10000 to base cost."""
        from qubitcoin.qvm.opcodes import get_quantum_gas_cost, Opcode
        cost = get_quantum_gas_cost(Opcode.QGATE, n_qubits=1)
        base = 5000  # QGATE base cost
        assert cost == base + 5000 * 2

    def test_two_qubit_cost(self):
        """2-qubit operation adds 5000 * 2^2 = 20000."""
        from qubitcoin.qvm.opcodes import get_quantum_gas_cost, Opcode
        cost = get_quantum_gas_cost(Opcode.QGATE, n_qubits=2)
        base = 5000
        assert cost == base + 5000 * 4

    def test_four_qubit_cost(self):
        """4-qubit operation adds 5000 * 2^4 = 80000."""
        from qubitcoin.qvm.opcodes import get_quantum_gas_cost, Opcode
        cost = get_quantum_gas_cost(Opcode.QGATE, n_qubits=4)
        base = 5000
        assert cost == base + 5000 * 16

    def test_exponential_growth(self):
        """Each additional qubit should roughly double the scaling cost."""
        from qubitcoin.qvm.opcodes import get_quantum_gas_cost, Opcode
        base = 5000
        cost_1 = get_quantum_gas_cost(Opcode.QGATE, n_qubits=1) - base
        cost_2 = get_quantum_gas_cost(Opcode.QGATE, n_qubits=2) - base
        cost_3 = get_quantum_gas_cost(Opcode.QGATE, n_qubits=3) - base
        assert cost_2 == cost_1 * 2
        assert cost_3 == cost_2 * 2

    def test_non_quantum_opcode_unchanged(self):
        """Non-quantum opcodes should not get scaling."""
        from qubitcoin.qvm.opcodes import get_quantum_gas_cost, Opcode, get_gas_cost
        add_cost = get_quantum_gas_cost(Opcode.ADD, n_qubits=10)
        assert add_cost == get_gas_cost(Opcode.ADD)

    def test_qvqe_high_cost(self):
        """VQE with 4 qubits should be very expensive."""
        from qubitcoin.qvm.opcodes import get_quantum_gas_cost, Opcode
        cost = get_quantum_gas_cost(Opcode.QVQE, n_qubits=4)
        base = 50000  # QVQE base cost
        assert cost == base + 5000 * 16
        assert cost > 100000

    def test_zero_qubits_treated_as_one(self):
        """0 qubits should be treated as minimum 1."""
        from qubitcoin.qvm.opcodes import get_quantum_gas_cost, Opcode
        cost_0 = get_quantum_gas_cost(Opcode.QGATE, n_qubits=0)
        cost_1 = get_quantum_gas_cost(Opcode.QGATE, n_qubits=1)
        assert cost_0 == cost_1

    def test_max_qubits_capped(self):
        """Qubits capped at 32 to prevent overflow."""
        from qubitcoin.qvm.opcodes import get_quantum_gas_cost, Opcode
        cost = get_quantum_gas_cost(Opcode.QGATE, n_qubits=100)
        cost_32 = get_quantum_gas_cost(Opcode.QGATE, n_qubits=32)
        assert cost == cost_32

    def test_all_quantum_opcodes_in_set(self):
        """All quantum opcodes should be in QUANTUM_OPCODES set."""
        from qubitcoin.qvm.opcodes import QUANTUM_OPCODES, Opcode
        expected = {
            Opcode.QGATE, Opcode.QMEASURE, Opcode.QENTANGLE,
            Opcode.QSUPERPOSE, Opcode.QVQE, Opcode.QHAMILTONIAN,
            Opcode.QENERGY, Opcode.QPROOF, Opcode.QFIDELITY,
            Opcode.QCREATE,
        }
        assert QUANTUM_OPCODES == expected

    def test_qdilithium_not_quantum_scaled(self):
        """QDILITHIUM is a precompile, should not scale with qubits."""
        from qubitcoin.qvm.opcodes import get_quantum_gas_cost, Opcode, get_gas_cost
        cost = get_quantum_gas_cost(Opcode.QDILITHIUM, n_qubits=10)
        assert cost == get_gas_cost(Opcode.QDILITHIUM)

    def test_base_gas_cost_unchanged(self):
        """Original get_gas_cost should still work unchanged."""
        from qubitcoin.qvm.opcodes import get_gas_cost, Opcode
        assert get_gas_cost(Opcode.ADD) == 3
        # EIP-2929: SSTORE gas is now charged dynamically (warm/cold tracking)
        assert get_gas_cost(Opcode.SSTORE) == 0  # Base cost 0; actual cost computed at runtime
        assert get_gas_cost(Opcode.QGATE) == 5000
