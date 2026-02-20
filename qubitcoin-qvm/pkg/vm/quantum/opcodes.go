// Package quantum implements QVM quantum opcode extensions.
//
// The quantum package provides 10 opcodes (0xF0-0xF9 canonical mapping)
// that extend the EVM with quantum state persistence, entanglement-based
// communication, compliance enforcement, risk assessment, and cross-chain
// bridge verification.
//
// These opcodes map to the QVM whitepaper specification:
//
//	QCREATE (0xF0) — Create quantum state as density matrix
//	QMEASURE (0xF1) — Measure quantum state (collapse)
//	QENTANGLE (0xF2) — Create entangled pair between contracts
//	QGATE (0xF3) — Apply quantum gate to state
//	QVERIFY (0xF4) — Verify quantum proof
//	QCOMPLIANCE (0xF5) — KYC/AML/sanctions check
//	QRISK (0xF6) — SUSY risk score for address
//	QRISK_SYSTEMIC (0xF7) — Systemic risk (contagion model)
//	QBRIDGE_ENTANGLE (0xF8) — Cross-chain quantum entanglement
//	QBRIDGE_VERIFY (0xF9) — Verify cross-chain bridge proof
package quantum

// QuantumOpcode represents a QVM quantum extension opcode.
type QuantumOpcode byte

// Canonical quantum opcode mapping (QVM Whitepaper).
const (
	QCREATE          QuantumOpcode = 0xF0
	QMEASURE         QuantumOpcode = 0xF1
	QENTANGLE        QuantumOpcode = 0xF2
	QGATE            QuantumOpcode = 0xF3
	QVERIFY          QuantumOpcode = 0xF4
	QCOMPLIANCE      QuantumOpcode = 0xF5
	QRISK            QuantumOpcode = 0xF6
	QRISK_SYSTEMIC   QuantumOpcode = 0xF7
	QBRIDGE_ENTANGLE QuantumOpcode = 0xF8
	QBRIDGE_VERIFY   QuantumOpcode = 0xF9
)

// QuantumGasCost maps quantum opcodes to their gas costs.
var QuantumGasCost = map[QuantumOpcode]uint64{
	QCREATE:          5000,  // + 5000 * 2^n_qubits
	QMEASURE:         3000,
	QENTANGLE:        10000,
	QGATE:            2000,
	QVERIFY:          8000,
	QCOMPLIANCE:      15000,
	QRISK:            5000,
	QRISK_SYSTEMIC:   10000,
	QBRIDGE_ENTANGLE: 20000,
	QBRIDGE_VERIFY:   15000,
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
