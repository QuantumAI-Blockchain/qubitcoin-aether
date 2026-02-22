"""
QVM Opcode Definitions
Full EVM opcode set + Qubitcoin quantum opcodes (0xd0-0xdf)
"""
from enum import IntEnum


class Opcode(IntEnum):
    # ========================================================================
    # STOP & ARITHMETIC (0x00-0x0b)
    # ========================================================================
    STOP = 0x00
    ADD = 0x01
    MUL = 0x02
    SUB = 0x03
    DIV = 0x04
    SDIV = 0x05
    MOD = 0x06
    SMOD = 0x07
    ADDMOD = 0x08
    MULMOD = 0x09
    EXP = 0x0a
    SIGNEXTEND = 0x0b

    # ========================================================================
    # COMPARISON & BITWISE (0x10-0x1d)
    # ========================================================================
    LT = 0x10
    GT = 0x11
    SLT = 0x12
    SGT = 0x13
    EQ = 0x14
    ISZERO = 0x15
    AND = 0x16
    OR = 0x17
    XOR = 0x18
    NOT = 0x19
    BYTE = 0x1a
    SHL = 0x1b
    SHR = 0x1c
    SAR = 0x1d

    # ========================================================================
    # KECCAK (0x20)
    # ========================================================================
    KECCAK256 = 0x20

    # ========================================================================
    # ENVIRONMENT (0x30-0x3f)
    # ========================================================================
    ADDRESS = 0x30
    BALANCE = 0x31
    ORIGIN = 0x32
    CALLER = 0x33
    CALLVALUE = 0x34
    CALLDATALOAD = 0x35
    CALLDATASIZE = 0x36
    CALLDATACOPY = 0x37
    CODESIZE = 0x38
    CODECOPY = 0x39
    GASPRICE = 0x3a
    EXTCODESIZE = 0x3b
    EXTCODECOPY = 0x3c
    RETURNDATASIZE = 0x3d
    RETURNDATACOPY = 0x3e
    EXTCODEHASH = 0x3f

    # ========================================================================
    # BLOCK INFO (0x40-0x48)
    # ========================================================================
    BLOCKHASH = 0x40
    COINBASE = 0x41
    TIMESTAMP = 0x42
    NUMBER = 0x43
    PREVRANDAO = 0x44
    GASLIMIT = 0x45
    CHAINID = 0x46
    SELFBALANCE = 0x47
    BASEFEE = 0x48

    # ========================================================================
    # STACK, MEMORY, STORAGE, FLOW (0x50-0x5b)
    # ========================================================================
    POP = 0x50
    MLOAD = 0x51
    MSTORE = 0x52
    MSTORE8 = 0x53
    SLOAD = 0x54
    SSTORE = 0x55
    JUMP = 0x56
    JUMPI = 0x57
    PC = 0x58
    MSIZE = 0x59
    GAS = 0x5a
    JUMPDEST = 0x5b

    # ========================================================================
    # PUSH (0x5f-0x7f)
    # ========================================================================
    PUSH0 = 0x5f
    PUSH1 = 0x60
    PUSH2 = 0x61
    PUSH3 = 0x62
    PUSH4 = 0x63
    PUSH5 = 0x64
    PUSH6 = 0x65
    PUSH7 = 0x66
    PUSH8 = 0x67
    PUSH9 = 0x68
    PUSH10 = 0x69
    PUSH11 = 0x6a
    PUSH12 = 0x6b
    PUSH13 = 0x6c
    PUSH14 = 0x6d
    PUSH15 = 0x6e
    PUSH16 = 0x6f
    PUSH17 = 0x70
    PUSH18 = 0x71
    PUSH19 = 0x72
    PUSH20 = 0x73
    PUSH21 = 0x74
    PUSH22 = 0x75
    PUSH23 = 0x76
    PUSH24 = 0x77
    PUSH25 = 0x78
    PUSH26 = 0x79
    PUSH27 = 0x7a
    PUSH28 = 0x7b
    PUSH29 = 0x7c
    PUSH30 = 0x7d
    PUSH31 = 0x7e
    PUSH32 = 0x7f

    # ========================================================================
    # DUP (0x80-0x8f)
    # ========================================================================
    DUP1 = 0x80
    DUP2 = 0x81
    DUP3 = 0x82
    DUP4 = 0x83
    DUP5 = 0x84
    DUP6 = 0x85
    DUP7 = 0x86
    DUP8 = 0x87
    DUP9 = 0x88
    DUP10 = 0x89
    DUP11 = 0x8a
    DUP12 = 0x8b
    DUP13 = 0x8c
    DUP14 = 0x8d
    DUP15 = 0x8e
    DUP16 = 0x8f

    # ========================================================================
    # SWAP (0x90-0x9f)
    # ========================================================================
    SWAP1 = 0x90
    SWAP2 = 0x91
    SWAP3 = 0x92
    SWAP4 = 0x93
    SWAP5 = 0x94
    SWAP6 = 0x95
    SWAP7 = 0x96
    SWAP8 = 0x97
    SWAP9 = 0x98
    SWAP10 = 0x99
    SWAP11 = 0x9a
    SWAP12 = 0x9b
    SWAP13 = 0x9c
    SWAP14 = 0x9d
    SWAP15 = 0x9e
    SWAP16 = 0x9f

    # ========================================================================
    # LOG (0xa0-0xa4)
    # ========================================================================
    LOG0 = 0xa0
    LOG1 = 0xa1
    LOG2 = 0xa2
    LOG3 = 0xa3
    LOG4 = 0xa4

    # ========================================================================
    # QUANTUM OPCODES (0xd0-0xde) - Qubitcoin extensions
    #
    # Current Python mapping (0xD0-0xDE): Active implementation
    # Whitepaper canonical mapping (0xF0-0xF9): Reserved for Go production build
    # Note: 0xF0-0xF5/0xFA are occupied by EVM system opcodes (CREATE, CALL, etc.)
    # so the Python implementation uses 0xD0-0xDE to avoid collisions.
    # The Go build will remap system opcodes to reconcile.
    #
    # Canonical mapping (whitepaper → Python):
    #   QCREATE    (WP:0xF0) → 0xDA  (create quantum state as density matrix)
    #   QMEASURE   (WP:0xF1) → 0xD1  (measure qubit, collapse)
    #   QENTANGLE  (WP:0xF2) → 0xD2  (create entangled pair)
    #   QGATE      (WP:0xF3) → 0xD0  (apply quantum gate)
    #   QVERIFY    (WP:0xF4) → 0xDB  (verify quantum proof — ZK)
    #   QCOMPLIANCE(WP:0xF5) → 0xDC  (KYC/AML/sanctions check)
    #   QRISK      (WP:0xF6) → 0xDD  (SUSY risk score for address)
    #   QRISK_SYS  (WP:0xF7) → 0xDE  (systemic risk / contagion)
    #   QBRIDGE_ENT(WP:0xF8) → (reserved, not yet implemented)
    #   QBRIDGE_VER(WP:0xF9) → (reserved, not yet implemented)
    # ========================================================================
    QGATE = 0xd0         # Apply quantum gate to qubit register
    QMEASURE = 0xd1      # Measure qubit, collapse to classical bit
    QENTANGLE = 0xd2     # Entangle two qubit registers
    QSUPERPOSE = 0xd3    # Put qubit into superposition
    QVQE = 0xd4          # Execute VQE optimization
    QHAMILTONIAN = 0xd5  # Load/generate Hamiltonian
    QENERGY = 0xd6       # Compute energy expectation value
    QPROOF = 0xd7        # Validate quantum proof
    QFIDELITY = 0xd8     # Compute state fidelity
    QDILITHIUM = 0xd9    # Verify Dilithium signature (precompile)
    QCREATE = 0xda       # Create quantum state as density matrix (WP: 0xF0)
    QVERIFY = 0xdb       # Verify quantum ZK proof (WP: 0xF4)
    QCOMPLIANCE = 0xdc   # KYC/AML/sanctions pre-flight check (WP: 0xF5)
    QRISK = 0xdd         # SUSY risk score for individual address (WP: 0xF6)
    QRISK_SYSTEMIC = 0xde  # Systemic risk / contagion model (WP: 0xF7)
    QBRIDGE_ENTANGLE = 0xc0  # Cross-chain quantum entanglement (WP: 0xF8)
    QBRIDGE_VERIFY = 0xc1    # Cross-chain bridge proof verification (WP: 0xF9)

    # ========================================================================
    # AETHER AGI OPCODES (0xc2-0xc3) - Smart contract ↔ AGI bridge
    # ========================================================================
    QREASON = 0xc2   # Query Aether reasoning engine from smart contract
    QPHI = 0xc3      # Read current Phi consciousness metric on-chain

    # ========================================================================
    # SYSTEM (0xf0-0xff)
    # ========================================================================
    CREATE = 0xf0
    CALL = 0xf1
    CALLCODE = 0xf2
    RETURN = 0xf3
    DELEGATECALL = 0xf4
    CREATE2 = 0xf5
    STATICCALL = 0xfa
    REVERT = 0xfd
    INVALID = 0xfe
    SELFDESTRUCT = 0xff


# Base gas costs per opcode
GAS_COSTS = {
    Opcode.STOP: 0,
    Opcode.ADD: 3, Opcode.MUL: 5, Opcode.SUB: 3, Opcode.DIV: 5,
    Opcode.SDIV: 5, Opcode.MOD: 5, Opcode.SMOD: 5,
    Opcode.ADDMOD: 8, Opcode.MULMOD: 8,
    Opcode.EXP: 10, Opcode.SIGNEXTEND: 5,
    Opcode.LT: 3, Opcode.GT: 3, Opcode.SLT: 3, Opcode.SGT: 3,
    Opcode.EQ: 3, Opcode.ISZERO: 3,
    Opcode.AND: 3, Opcode.OR: 3, Opcode.XOR: 3, Opcode.NOT: 3,
    Opcode.BYTE: 3, Opcode.SHL: 3, Opcode.SHR: 3, Opcode.SAR: 3,
    Opcode.KECCAK256: 30,
    Opcode.ADDRESS: 2, Opcode.BALANCE: 700, Opcode.ORIGIN: 2,
    Opcode.CALLER: 2, Opcode.CALLVALUE: 2,
    Opcode.CALLDATALOAD: 3, Opcode.CALLDATASIZE: 2, Opcode.CALLDATACOPY: 3,
    Opcode.CODESIZE: 2, Opcode.CODECOPY: 3,
    Opcode.GASPRICE: 2, Opcode.EXTCODESIZE: 700,
    Opcode.EXTCODECOPY: 700, Opcode.RETURNDATASIZE: 2, Opcode.RETURNDATACOPY: 3,
    Opcode.EXTCODEHASH: 700,
    Opcode.BLOCKHASH: 20, Opcode.COINBASE: 2, Opcode.TIMESTAMP: 2,
    Opcode.NUMBER: 2, Opcode.PREVRANDAO: 2, Opcode.GASLIMIT: 2,
    Opcode.CHAINID: 2, Opcode.SELFBALANCE: 5, Opcode.BASEFEE: 2,
    Opcode.POP: 2, Opcode.MLOAD: 3, Opcode.MSTORE: 3, Opcode.MSTORE8: 3,
    Opcode.SLOAD: 800, Opcode.SSTORE: 20000,
    Opcode.JUMP: 8, Opcode.JUMPI: 10, Opcode.PC: 2, Opcode.MSIZE: 2,
    Opcode.GAS: 2, Opcode.JUMPDEST: 1,
    Opcode.PUSH0: 2,
    Opcode.LOG0: 375, Opcode.LOG1: 750, Opcode.LOG2: 1125,
    Opcode.LOG3: 1500, Opcode.LOG4: 1875,
    # Quantum opcodes (higher cost - quantum operations are expensive)
    Opcode.QGATE: 5000, Opcode.QMEASURE: 3000,
    Opcode.QENTANGLE: 8000, Opcode.QSUPERPOSE: 4000,
    Opcode.QVQE: 50000, Opcode.QHAMILTONIAN: 10000,
    Opcode.QENERGY: 15000, Opcode.QPROOF: 25000,
    Opcode.QFIDELITY: 10000, Opcode.QDILITHIUM: 3000,
    Opcode.QCREATE: 5000, Opcode.QVERIFY: 8000,
    Opcode.QCOMPLIANCE: 15000, Opcode.QRISK: 5000, Opcode.QRISK_SYSTEMIC: 10000,
    Opcode.QBRIDGE_ENTANGLE: 20000, Opcode.QBRIDGE_VERIFY: 15000,
    Opcode.QREASON: 25000, Opcode.QPHI: 5000,
    # System
    Opcode.CREATE: 32000, Opcode.CALL: 700, Opcode.CALLCODE: 700,
    Opcode.RETURN: 0, Opcode.DELEGATECALL: 700, Opcode.CREATE2: 32000,
    Opcode.STATICCALL: 700, Opcode.REVERT: 0,
    Opcode.INVALID: 0, Opcode.SELFDESTRUCT: 5000,
}

# Default 3 gas for all PUSH/DUP/SWAP
for i in range(0x60, 0x80):  # PUSH1-PUSH32
    GAS_COSTS[i] = 3
for i in range(0x80, 0x90):  # DUP1-DUP16
    GAS_COSTS[i] = 3
for i in range(0x90, 0xa0):  # SWAP1-SWAP16
    GAS_COSTS[i] = 3


def get_gas_cost(opcode: int) -> int:
    """Get gas cost for an opcode"""
    return GAS_COSTS.get(opcode, 0)


# Quantum opcodes that support n-qubit scaling
QUANTUM_OPCODES = {
    Opcode.QGATE, Opcode.QMEASURE, Opcode.QENTANGLE,
    Opcode.QSUPERPOSE, Opcode.QVQE, Opcode.QHAMILTONIAN,
    Opcode.QENERGY, Opcode.QPROOF, Opcode.QFIDELITY,
    Opcode.QCREATE,
}

# Canonical whitepaper mapping (0xF0-0xF9) → current Python opcodes
# Used for documentation and future Go migration
CANONICAL_OPCODE_MAP = {
    0xF0: Opcode.QCREATE,       # Create quantum state (density matrix)
    0xF1: Opcode.QMEASURE,      # Measure quantum state (collapse)
    0xF2: Opcode.QENTANGLE,     # Create entangled pair
    0xF3: Opcode.QGATE,         # Apply quantum gate
    0xF4: Opcode.QVERIFY,       # Verify quantum proof (ZK)
    0xF5: Opcode.QCOMPLIANCE,   # KYC/AML/sanctions check
    0xF6: Opcode.QRISK,         # SUSY risk score (address)
    0xF7: Opcode.QRISK_SYSTEMIC,  # Systemic risk (contagion)
    0xF8: Opcode.QBRIDGE_ENTANGLE,  # Cross-chain quantum entanglement
    0xF9: Opcode.QBRIDGE_VERIFY,    # Cross-chain bridge proof verification
}


def get_quantum_gas_cost(opcode: int, n_qubits: int = 1) -> int:
    """Get gas cost for a quantum opcode with exponential scaling.

    Quantum operations scale as: base_cost + 5000 * 2^n_qubits.
    This prevents DOS attacks via expensive multi-qubit operations
    while keeping single-qubit operations affordable.

    Args:
        opcode: The quantum opcode.
        n_qubits: Number of qubits involved in the operation.

    Returns:
        Total gas cost for the quantum operation.
    """
    base_cost = GAS_COSTS.get(opcode, 0)
    if opcode not in QUANTUM_OPCODES:
        return base_cost
    if n_qubits < 1:
        n_qubits = 1
    # Cap at 32 qubits to prevent integer overflow
    n_qubits = min(n_qubits, 32)
    scaling_cost = 5000 * (2 ** n_qubits)
    return base_cost + scaling_cost


# Maximum values
MAX_UINT256 = (1 << 256) - 1
MAX_INT256 = (1 << 255) - 1
MIN_INT256 = -(1 << 255)
UINT256_MOD = 1 << 256


def to_signed(value: int) -> int:
    """Convert unsigned 256-bit to signed"""
    if value > MAX_INT256:
        return value - UINT256_MOD
    return value


def to_unsigned(value: int) -> int:
    """Convert signed to unsigned 256-bit"""
    return value % UINT256_MOD
