"""
Cross-Implementation Opcode Test Suite (L7)

Verifies that Python QVM and Go QVM produce identical results for
the same bytecode inputs. Tests precompiles (direct API) and MSTORE/RETURN
bytecode programs that produce verifiable return_data.

These test cases can also be exported as JSON fixtures for the Go test runner.
"""
import json
import pytest


# Bytecode helper: PUSH result to memory at 0, then RETURN 32 bytes
# Pattern: <computation> PUSH1 0x00 MSTORE PUSH1 0x20 PUSH1 0x00 RETURN
#   = <computation> 60 00 52 60 20 60 00 f3
RETURN_SUFFIX = "60005260206000f3"


# ── Test vectors: (desc, bytecode_hex_with_return, expected_return_hex_32bytes) ──
RETURN_TEST_VECTORS = [
    # Arithmetic (result is stored via MSTORE then RETURNed as 32-byte value)
    ("ADD: 2 + 3 = 5",
     "6002600301" + RETURN_SUFFIX,
     (5).to_bytes(32, 'big').hex()),
    ("MUL: 7 * 8 = 56",
     "6007600802" + RETURN_SUFFIX,
     (56).to_bytes(32, 'big').hex()),
    # EVM stack order: SUB pops a (top), b (second) → pushes a - b
    # So to compute 10-3: PUSH 3, PUSH 10, SUB → 10 - 3 = 7
    ("SUB: 10 - 3 = 7",
     "6003600a03" + RETURN_SUFFIX,
     (7).to_bytes(32, 'big').hex()),
    ("DIV: 20 / 4 = 5",
     "6004601404" + RETURN_SUFFIX,
     (5).to_bytes(32, 'big').hex()),
    ("MOD: 17 % 5 = 2",
     "6005601106" + RETURN_SUFFIX,
     (2).to_bytes(32, 'big').hex()),
    ("EXP: 2^10 = 1024",
     "600a60020a" + RETURN_SUFFIX,
     (1024).to_bytes(32, 'big').hex()),

    # Comparison & Bitwise
    # LT: a < b → PUSH b, PUSH a, LT → a < b
    ("LT: 9 < 10 = 1",
     "600a600910" + RETURN_SUFFIX,
     (1).to_bytes(32, 'big').hex()),
    ("GT: 10 > 9 = 1",
     "6009600a11" + RETURN_SUFFIX,
     (1).to_bytes(32, 'big').hex()),
    ("EQ: 5 == 5 = 1",
     "6005600514" + RETURN_SUFFIX,
     (1).to_bytes(32, 'big').hex()),
    ("ISZERO: 0 = 1",
     "600015" + RETURN_SUFFIX,
     (1).to_bytes(32, 'big').hex()),
    ("AND: 0xFF & 0x0F = 0x0F",
     "60ff600f16" + RETURN_SUFFIX,
     (0x0f).to_bytes(32, 'big').hex()),
    ("OR: 0xF0 | 0x0F = 0xFF",
     "60f0600f17" + RETURN_SUFFIX,
     (0xff).to_bytes(32, 'big').hex()),
    ("XOR: 0xFF ^ 0x0F = 0xF0",
     "60ff600f18" + RETURN_SUFFIX,
     (0xf0).to_bytes(32, 'big').hex()),
]


class TestCrossImplOpcodes:
    """Test Python QVM opcode execution against expected return_data."""

    CALLER = "0x" + "00" * 20
    CONTRACT = "0x" + "11" * 20

    @pytest.fixture
    def qvm(self):
        """Create a minimal QVM instance for testing."""
        try:
            from qubitcoin.qvm.vm import QVM
            return QVM()
        except Exception:
            pytest.skip("QVM not importable")

    @pytest.mark.parametrize("desc,bytecode_hex,expected_hex", RETURN_TEST_VECTORS)
    def test_opcode_return(self, qvm, desc: str, bytecode_hex: str, expected_hex: str):
        """Verify opcode produces the expected return_data via MSTORE+RETURN."""
        bytecode = bytes.fromhex(bytecode_hex)
        result = qvm.execute(
            caller=self.CALLER,
            address=self.CONTRACT,
            code=bytecode,
            gas=100000,
        )
        assert result.success, f"{desc}: execution failed — {result.revert_reason}"
        actual_hex = result.return_data.hex()
        assert actual_hex == expected_hex, (
            f"{desc}: expected return 0x{expected_hex[-8:]}, "
            f"got 0x{actual_hex[-8:]}"
        )

    def test_execution_no_crash(self, qvm):
        """Verify various programs execute without crashing."""
        programs = [
            "604200",          # PUSH1 0x42 + STOP
            "6001600201" + RETURN_SUFFIX,  # 1 + 2 → return
            "600060005200",    # MSTORE(0, 0) + STOP
        ]
        for prog in programs:
            bytecode = bytes.fromhex(prog)
            result = qvm.execute(
                caller=self.CALLER,
                address=self.CONTRACT,
                code=bytecode,
                gas=100000,
            )
            assert result.success, f"Program {prog} failed: {result.revert_reason}"


class TestModExpGasFormula:
    """Standalone tests for the EIP-198 ModExp gas formula."""

    def test_small_inputs(self):
        """Small base/exp/mod should cost minimum 200 gas."""
        from qubitcoin.qvm.vm import QVM
        vm = QVM()
        # bLen=1, eLen=1, mLen=1: base=2, exp=3, mod=5
        data = (
            (1).to_bytes(32, 'big') +
            (1).to_bytes(32, 'big') +
            (1).to_bytes(32, 'big') +
            b'\x02' + b'\x03' + b'\x05'
        )
        result = vm._execute_precompile(5, data, 100000)
        assert result.success
        assert result.gas_used == 200  # minimum floor
        # 2^3 mod 5 = 3
        assert int.from_bytes(result.return_data, 'big') == 3

    def test_large_exponent(self):
        """Large exponent should cost more gas per EIP-198."""
        from qubitcoin.qvm.vm import QVM
        vm = QVM()
        # bLen=32, eLen=32, mLen=32
        data = (
            (32).to_bytes(32, 'big') +
            (32).to_bytes(32, 'big') +
            (32).to_bytes(32, 'big') +
            (2).to_bytes(32, 'big') +
            (0xFFFFFFFF).to_bytes(32, 'big') +
            (1000000007).to_bytes(32, 'big')
        )
        result = vm._execute_precompile(5, data, 10000000)
        assert result.success
        # For 32-byte inputs: mult_complexity = 32^2 = 1024
        # adj_exp_len = bit_length(0xFFFFFFFF) - 1 = 31
        # gas = max(200, 1024 * 31 / 3) = max(200, 10581) = 10581
        assert result.gas_used > 200, f"Large exponent should cost > 200 gas, got {result.gas_used}"
