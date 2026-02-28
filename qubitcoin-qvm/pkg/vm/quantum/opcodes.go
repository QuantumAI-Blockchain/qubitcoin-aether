// Package quantum implements QVM quantum and AGI opcode extensions.
//
// The quantum package provides 10 quantum opcodes and 2 AGI opcodes
// that extend the EVM with quantum state persistence, entanglement-based
// communication, compliance enforcement, risk assessment, cross-chain
// bridge verification, and on-chain AGI reasoning and consciousness queries.
//
// Opcode mapping uses the 0xC0-0xDE range to avoid collisions with EVM
// system opcodes at 0xF0-0xFF (CREATE, CALL, RETURN, DELEGATECALL, etc.).
// This mapping is shared with the Python QVM for bytecode compatibility.
//
// Whitepaper canonical mapping (0xF0-0xF9) is preserved in
// CanonicalOpcodeMap for documentation; runtime uses 0xC0-0xDE.
//
//	QGATE (0xD0)            — Apply quantum gate to state
//	QMEASURE (0xD1)         — Measure quantum state (collapse)
//	QENTANGLE (0xD2)        — Create entangled pair between contracts
//	QSUPERPOSE (0xD3)       — Put qubit into superposition
//	QVQE (0xD4)             — Execute VQE optimization
//	QHAMILTONIAN (0xD5)     — Load/generate Hamiltonian
//	QENERGY (0xD6)          — Compute energy expectation value
//	QPROOF (0xD7)           — Validate quantum proof
//	QFIDELITY (0xD8)        — Compute state fidelity
//	QDILITHIUM (0xD9)       — Verify Dilithium signature
//	QCREATE (0xDA)          — Create quantum state as density matrix
//	QVERIFY (0xDB)          — Verify quantum ZK proof
//	QCOMPLIANCE (0xDC)      — KYC/AML/sanctions check
//	QRISK (0xDD)            — SUSY risk score for address
//	QRISK_SYSTEMIC (0xDE)   — Systemic risk (contagion model)
//	QBRIDGE_ENTANGLE (0xC0) — Cross-chain quantum entanglement
//	QBRIDGE_VERIFY (0xC1)   — Cross-chain bridge proof verification
//	QREASON (0xC2)          — On-chain AGI reasoning query
//	QPHI (0xC3)             — Consciousness metric (Phi) query
package quantum

// QuantumOpcode represents a QVM quantum extension opcode.
type QuantumOpcode byte

// Runtime quantum opcode mapping — matches Python QVM for bytecode compatibility.
// Uses 0xC0-0xDE range to avoid EVM system opcode collisions at 0xF0-0xFF.
const (
	QGATE            QuantumOpcode = 0xD0 // Apply quantum gate
	QMEASURE         QuantumOpcode = 0xD1 // Measure qubit (collapse)
	QENTANGLE        QuantumOpcode = 0xD2 // Entangle two registers
	QSUPERPOSE       QuantumOpcode = 0xD3 // Superposition
	QVQE             QuantumOpcode = 0xD4 // VQE optimization
	QHAMILTONIAN     QuantumOpcode = 0xD5 // Hamiltonian generation
	QENERGY          QuantumOpcode = 0xD6 // Energy expectation
	QPROOF           QuantumOpcode = 0xD7 // Validate quantum proof
	QFIDELITY        QuantumOpcode = 0xD8 // State fidelity
	QDILITHIUM       QuantumOpcode = 0xD9 // Dilithium signature verify
	QCREATE          QuantumOpcode = 0xDA // Create quantum state (density matrix)
	QVERIFY          QuantumOpcode = 0xDB // Verify quantum ZK proof
	QCOMPLIANCE      QuantumOpcode = 0xDC // KYC/AML/sanctions check
	QRISK            QuantumOpcode = 0xDD // SUSY risk score
	QRISK_SYSTEMIC   QuantumOpcode = 0xDE // Systemic risk (contagion)
	QBRIDGE_ENTANGLE QuantumOpcode = 0xC0 // Cross-chain entanglement
	QBRIDGE_VERIFY   QuantumOpcode = 0xC1 // Cross-chain bridge proof

	// AGI opcodes (Aether Tree integration).
	QREASON QuantumOpcode = 0xC2 // On-chain reasoning query
	QPHI    QuantumOpcode = 0xC3 // Consciousness metric (Phi) query
)

// QuantumGasCost maps quantum and AGI opcodes to their base gas costs.
// Quantum opcodes with qubit scaling add 5000 * 2^n_qubits on top.
var QuantumGasCost = map[QuantumOpcode]uint64{
	QGATE:            5000,  // Apply quantum gate
	QMEASURE:         3000,  // Measure qubit
	QENTANGLE:        8000,  // Entangle registers
	QSUPERPOSE:       4000,  // Superposition
	QVQE:             50000, // VQE optimization (expensive)
	QHAMILTONIAN:     10000, // Hamiltonian generation
	QENERGY:          15000, // Energy expectation
	QPROOF:           25000, // Validate quantum proof
	QFIDELITY:        10000, // State fidelity
	QDILITHIUM:       3000,  // Dilithium signature verify
	QCREATE:          5000,  // + 5000 * 2^n_qubits
	QVERIFY:          8000,  // Verify quantum ZK proof
	QCOMPLIANCE:      15000, // KYC/AML/sanctions check
	QRISK:            5000,  // SUSY risk score
	QRISK_SYSTEMIC:   10000, // Systemic risk
	QBRIDGE_ENTANGLE: 20000, // Cross-chain entanglement
	QBRIDGE_VERIFY:   15000, // Bridge proof verification

	// AGI opcodes
	QREASON: 50000, // On-chain reasoning is computationally expensive
	QPHI:    5000,  // Consciousness metric read
}

// CanonicalOpcodeMap preserves the whitepaper mapping (0xF0-0xF9) for reference.
// Runtime uses 0xC0-0xDE to avoid EVM system opcode collisions.
var CanonicalOpcodeMap = map[byte]QuantumOpcode{
	0xF0: QCREATE,
	0xF1: QMEASURE,
	0xF2: QENTANGLE,
	0xF3: QGATE,
	0xF4: QVERIFY,
	0xF5: QCOMPLIANCE,
	0xF6: QRISK,
	0xF7: QRISK_SYSTEMIC,
	0xF8: QBRIDGE_ENTANGLE,
	0xF9: QBRIDGE_VERIFY,
}

// QuantumState represents a quantum state stored as a density matrix.
type QuantumState struct {
	ID        uint64
	NQubits   uint8
	Matrix    []complex128 // density matrix (2^n x 2^n)
	Entangled []uint64     // IDs of entangled states
	Measured  bool
	Owner     [20]byte // contract address
}

// EntanglementRecord tracks an entangled pair of quantum states.
type EntanglementRecord struct {
	StateA    uint64
	StateB    uint64
	CreatedAt uint64 // block number
	BellPair  bool   // true if maximally entangled
}
