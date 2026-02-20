package quantum

import (
	"fmt"
	"math"
	"math/cmplx"
)

// GateType represents a quantum gate.
type GateType uint8

const (
	GateH    GateType = 0 // Hadamard
	GateX    GateType = 1 // Pauli-X (NOT)
	GateY    GateType = 2 // Pauli-Y
	GateZ    GateType = 3 // Pauli-Z
	GateCNOT GateType = 4 // Controlled-NOT (2 qubits)
	GateRX   GateType = 5 // Rotation X (parameterized)
	GateRY   GateType = 6 // Rotation Y (parameterized)
	GateRZ   GateType = 7 // Rotation Z (parameterized)
	GateS    GateType = 8 // S gate (√Z)
	GateT    GateType = 9 // T gate (π/8)
)

// GateNames maps gate types to their string names.
var GateNames = map[GateType]string{
	GateH: "H", GateX: "X", GateY: "Y", GateZ: "Z",
	GateCNOT: "CNOT", GateRX: "RX", GateRY: "RY", GateRZ: "RZ",
	GateS: "S", GateT: "T",
}

// IsParameterized returns true if the gate requires an angle parameter.
func (g GateType) IsParameterized() bool {
	return g == GateRX || g == GateRY || g == GateRZ
}

// IsTwoQubit returns true if the gate operates on two qubits.
func (g GateType) IsTwoQubit() bool {
	return g == GateCNOT
}

// Gate2x2 returns the 2x2 unitary matrix for a single-qubit gate.
func Gate2x2(gateType GateType, theta float64) ([4]complex128, error) {
	var m [4]complex128

	switch gateType {
	case GateH:
		// H = (1/√2) * [[1, 1], [1, -1]]
		s := 1.0 / math.Sqrt(2.0)
		m = [4]complex128{
			complex(s, 0), complex(s, 0),
			complex(s, 0), complex(-s, 0),
		}

	case GateX:
		// X = [[0, 1], [1, 0]]
		m = [4]complex128{0, 1, 1, 0}

	case GateY:
		// Y = [[0, -i], [i, 0]]
		m = [4]complex128{0, complex(0, -1), complex(0, 1), 0}

	case GateZ:
		// Z = [[1, 0], [0, -1]]
		m = [4]complex128{1, 0, 0, -1}

	case GateRX:
		// RX(θ) = [[cos(θ/2), -i*sin(θ/2)], [-i*sin(θ/2), cos(θ/2)]]
		c := math.Cos(theta / 2)
		s := math.Sin(theta / 2)
		m = [4]complex128{
			complex(c, 0), complex(0, -s),
			complex(0, -s), complex(c, 0),
		}

	case GateRY:
		// RY(θ) = [[cos(θ/2), -sin(θ/2)], [sin(θ/2), cos(θ/2)]]
		c := math.Cos(theta / 2)
		s := math.Sin(theta / 2)
		m = [4]complex128{
			complex(c, 0), complex(-s, 0),
			complex(s, 0), complex(c, 0),
		}

	case GateRZ:
		// RZ(θ) = [[e^(-iθ/2), 0], [0, e^(iθ/2)]]
		m = [4]complex128{
			cmplx.Exp(complex(0, -theta/2)), 0,
			0, cmplx.Exp(complex(0, theta/2)),
		}

	case GateS:
		// S = [[1, 0], [0, i]]
		m = [4]complex128{1, 0, 0, complex(0, 1)}

	case GateT:
		// T = [[1, 0], [0, e^(iπ/4)]]
		m = [4]complex128{1, 0, 0, cmplx.Exp(complex(0, math.Pi/4))}

	default:
		return m, fmt.Errorf("unknown single-qubit gate type: %d", gateType)
	}

	return m, nil
}

// ApplyGate applies a single-qubit gate to the specified qubit of a quantum state.
// The gate operates on the density matrix: ρ' = U ρ U†
// where U = I ⊗ ... ⊗ gate ⊗ ... ⊗ I (gate at position qubitIdx).
func ApplyGate(state *QuantumState, gateType GateType, qubitIdx uint8, theta float64) error {
	if qubitIdx >= state.NQubits {
		return fmt.Errorf("qubit index %d out of range (state has %d qubits)", qubitIdx, state.NQubits)
	}
	if state.Measured {
		return fmt.Errorf("cannot apply gate to measured state")
	}

	gate, err := Gate2x2(gateType, theta)
	if err != nil {
		return err
	}

	dim := 1 << state.NQubits
	newMatrix := make([]complex128, dim*dim)

	// Build full unitary U = I ⊗ ... ⊗ gate ⊗ ... ⊗ I
	// Apply as ρ' = U ρ U†
	// We compute this element-by-element for correctness.
	//
	// For a single-qubit gate on qubit q:
	//   U|i⟩ = gate[bit_q(i), 0] * |i with bit_q=0⟩ + gate[bit_q(i), 1] * |i with bit_q=1⟩
	//
	// This is equivalent to iterating over all basis pairs and applying
	// the gate's 2x2 matrix on the relevant qubit dimension.

	targetBit := state.NQubits - 1 - qubitIdx // MSB ordering

	// First compute U ρ (apply gate to rows)
	temp := make([]complex128, dim*dim)
	for i := 0; i < dim; i++ {
		for j := 0; j < dim; j++ {
			// For row i, the gate maps qubit targetBit
			b := (i >> targetBit) & 1 // current bit value
			// Partner index: flip the target bit
			partner := i ^ (1 << targetBit)

			// U[i, i_orig] = gate[b, b_orig]
			// i comes from i_orig (same bit = b) with coefficient gate[b][b]
			// i comes from partner (bit flipped) with coefficient gate[b][1-b]
			temp[i*dim+j] = gate[b*2+b]*state.Matrix[i*dim+j] +
				gate[b*2+(1-b)]*state.Matrix[partner*dim+j]
		}
	}

	// Then compute (U ρ) U† (apply conjugate-transpose of gate to columns)
	for i := 0; i < dim; i++ {
		for j := 0; j < dim; j++ {
			b := (j >> targetBit) & 1
			partner := j ^ (1 << targetBit)

			// U†[j_orig, j] = conj(gate[j, j_orig]) = conj(gate[b_j, b_orig])
			newMatrix[i*dim+j] = cmplx.Conj(gate[b*2+b])*temp[i*dim+j] +
				cmplx.Conj(gate[(1-b)*2+b])*temp[i*dim+partner]
		}
	}

	state.Matrix = newMatrix
	return nil
}

// ApplyCNOT applies a CNOT (controlled-X) gate to a quantum state.
// control and target specify the qubit indices.
func ApplyCNOT(state *QuantumState, control, target uint8) error {
	if control >= state.NQubits || target >= state.NQubits {
		return fmt.Errorf("qubit index out of range")
	}
	if control == target {
		return fmt.Errorf("control and target must be different qubits")
	}
	if state.Measured {
		return fmt.Errorf("cannot apply gate to measured state")
	}

	dim := 1 << state.NQubits
	newMatrix := make([]complex128, dim*dim)

	controlBit := state.NQubits - 1 - control
	targetBit := state.NQubits - 1 - target

	// CNOT permutation: if control bit is 1, flip target bit
	// Build permutation map
	perm := make([]int, dim)
	for i := 0; i < dim; i++ {
		if (i>>controlBit)&1 == 1 {
			perm[i] = i ^ (1 << targetBit)
		} else {
			perm[i] = i
		}
	}

	// Apply permutation to density matrix: ρ' = P ρ P†
	// For a permutation matrix, P† = P^T = P^(-1), and P[perm[i], i] = 1.
	// So ρ'[i,j] = ρ[perm^(-1)[i], perm^(-1)[j]]
	// Since CNOT is its own inverse: perm^(-1) = perm.
	for i := 0; i < dim; i++ {
		for j := 0; j < dim; j++ {
			newMatrix[i*dim+j] = state.Matrix[perm[i]*dim+perm[j]]
		}
	}

	state.Matrix = newMatrix
	return nil
}
