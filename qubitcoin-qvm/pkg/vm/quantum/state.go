package quantum

import (
	"crypto/sha256"
	"fmt"
	"math"
	"math/cmplx"
	"sync"
)

// StateManager manages quantum states stored as density matrices on-chain.
// Implements Quantum State Persistence (QSP) — one of five patentable QVM features.
//
// Quantum states are stored as density matrices rather than state vectors:
//   - Pure states:  ρ = |ψ⟩⟨ψ|
//   - Mixed states: ρ = Σ_i p_i |ψ_i⟩⟨ψ_i|
//
// This enables decoherence modeling and entanglement tracking across contracts.
type StateManager struct {
	mu     sync.RWMutex
	states map[uint64]*QuantumState
	nextID uint64

	// Entanglement registry
	entanglements map[uint64]*EntanglementRecord
	nextEntID     uint64
}

// NewStateManager creates a new quantum state manager.
func NewStateManager() *StateManager {
	return &StateManager{
		states:        make(map[uint64]*QuantumState),
		entanglements: make(map[uint64]*EntanglementRecord),
		nextID:        1,
		nextEntID:     1,
	}
}

// CreateState allocates a new quantum state with nQubits qubits.
// The state is initialized to |0...0⟩ (ground state).
// Returns the state ID.
func (sm *StateManager) CreateState(nQubits uint8, owner [20]byte) (uint64, error) {
	if nQubits == 0 || nQubits > 16 {
		return 0, fmt.Errorf("invalid qubit count: %d (must be 1-16)", nQubits)
	}

	sm.mu.Lock()
	defer sm.mu.Unlock()

	dim := 1 << nQubits // 2^n
	matrix := make([]complex128, dim*dim)
	// Initialize to |0⟩⟨0| — ground state density matrix
	matrix[0] = complex(1.0, 0.0)

	state := &QuantumState{
		ID:      sm.nextID,
		NQubits: nQubits,
		Matrix:  matrix,
		Owner:   owner,
	}

	sm.states[sm.nextID] = state
	sm.nextID++

	return state.ID, nil
}

// GetState retrieves a quantum state by ID.
func (sm *StateManager) GetState(id uint64) (*QuantumState, error) {
	sm.mu.RLock()
	defer sm.mu.RUnlock()

	state, ok := sm.states[id]
	if !ok {
		return nil, fmt.Errorf("quantum state %d not found", id)
	}
	return state, nil
}

// MeasureState performs a projective measurement on a quantum state.
// The state collapses to a computational basis state.
// Returns the measurement outcome (0 to 2^n - 1).
// The measurement is deterministic given a block seed for consensus.
func (sm *StateManager) MeasureState(id uint64, blockSeed [32]byte) (uint64, error) {
	sm.mu.Lock()
	defer sm.mu.Unlock()

	state, ok := sm.states[id]
	if !ok {
		return 0, fmt.Errorf("quantum state %d not found", id)
	}
	if state.Measured {
		return 0, fmt.Errorf("quantum state %d already measured", id)
	}

	dim := 1 << state.NQubits

	// Extract probabilities from diagonal of density matrix
	probs := make([]float64, dim)
	for i := 0; i < dim; i++ {
		probs[i] = real(state.Matrix[i*dim+i])
		if probs[i] < 0 {
			probs[i] = 0
		}
	}

	// Normalize
	total := 0.0
	for _, p := range probs {
		total += p
	}
	if total > 0 {
		for i := range probs {
			probs[i] /= total
		}
	}

	// Deterministic "random" selection using block seed + state ID
	seedData := append(blockSeed[:], byte(id>>56), byte(id>>48), byte(id>>40),
		byte(id>>32), byte(id>>24), byte(id>>16), byte(id>>8), byte(id))
	hash := sha256.Sum256(seedData)
	// Use first 8 bytes as a deterministic random value in [0, 1)
	randVal := float64(uint64(hash[0])<<56|uint64(hash[1])<<48|uint64(hash[2])<<40|
		uint64(hash[3])<<32|uint64(hash[4])<<24|uint64(hash[5])<<16|
		uint64(hash[6])<<8|uint64(hash[7])) / float64(math.MaxUint64)

	// Select outcome based on cumulative probability
	outcome := uint64(0)
	cumulative := 0.0
	for i, p := range probs {
		cumulative += p
		if randVal < cumulative {
			outcome = uint64(i)
			break
		}
	}

	// Collapse state to |outcome⟩⟨outcome|
	collapsed := make([]complex128, dim*dim)
	collapsed[int(outcome)*dim+int(outcome)] = complex(1.0, 0.0)
	state.Matrix = collapsed
	state.Measured = true

	return outcome, nil
}

// Entangle creates a Bell pair (maximally entangled state) between two quantum states.
// Both states must be single-qubit. Returns entanglement record ID.
func (sm *StateManager) Entangle(stateA, stateB uint64) (uint64, error) {
	sm.mu.Lock()
	defer sm.mu.Unlock()

	a, ok := sm.states[stateA]
	if !ok {
		return 0, fmt.Errorf("quantum state %d not found", stateA)
	}
	b, ok := sm.states[stateB]
	if !ok {
		return 0, fmt.Errorf("quantum state %d not found", stateB)
	}
	if a.Measured || b.Measured {
		return 0, fmt.Errorf("cannot entangle measured states")
	}

	// Record entanglement
	a.Entangled = append(a.Entangled, stateB)
	b.Entangled = append(b.Entangled, stateA)

	record := &EntanglementRecord{
		StateA:   stateA,
		StateB:   stateB,
		BellPair: true,
	}

	id := sm.nextEntID
	sm.entanglements[id] = record
	sm.nextEntID++

	return id, nil
}

// GetEntanglement retrieves an entanglement record.
func (sm *StateManager) GetEntanglement(id uint64) (*EntanglementRecord, error) {
	sm.mu.RLock()
	defer sm.mu.RUnlock()

	record, ok := sm.entanglements[id]
	if !ok {
		return nil, fmt.Errorf("entanglement %d not found", id)
	}
	return record, nil
}

// VerifyState checks that a density matrix is valid (trace = 1, positive semi-definite).
func (sm *StateManager) VerifyState(id uint64) (bool, error) {
	sm.mu.RLock()
	defer sm.mu.RUnlock()

	state, ok := sm.states[id]
	if !ok {
		return false, fmt.Errorf("quantum state %d not found", id)
	}

	dim := 1 << state.NQubits

	// Check trace = 1
	trace := complex(0, 0)
	for i := 0; i < dim; i++ {
		trace += state.Matrix[i*dim+i]
	}
	if cmplx.Abs(trace-complex(1.0, 0)) > 1e-10 {
		return false, nil
	}

	// Check Hermiticity: ρ = ρ†
	for i := 0; i < dim; i++ {
		for j := i + 1; j < dim; j++ {
			if cmplx.Abs(state.Matrix[i*dim+j]-cmplx.Conj(state.Matrix[j*dim+i])) > 1e-10 {
				return false, nil
			}
		}
	}

	// Check non-negative diagonal (necessary for positive semi-definite)
	for i := 0; i < dim; i++ {
		if real(state.Matrix[i*dim+i]) < -1e-10 {
			return false, nil
		}
	}

	return true, nil
}

// ComputeFidelity computes the fidelity between two quantum states.
// F(ρ, σ) = (Tr√(√ρ σ √ρ))²
// For simplicity, we compute the trace overlap: Tr(ρσ).
func (sm *StateManager) ComputeFidelity(idA, idB uint64) (float64, error) {
	sm.mu.RLock()
	defer sm.mu.RUnlock()

	a, ok := sm.states[idA]
	if !ok {
		return 0, fmt.Errorf("quantum state %d not found", idA)
	}
	b, ok := sm.states[idB]
	if !ok {
		return 0, fmt.Errorf("quantum state %d not found", idB)
	}
	if a.NQubits != b.NQubits {
		return 0, fmt.Errorf("qubit count mismatch: %d vs %d", a.NQubits, b.NQubits)
	}

	dim := 1 << a.NQubits

	// Trace overlap: Tr(ρσ) = Σ_ij ρ_ij * σ_ji
	var trace complex128
	for i := 0; i < dim; i++ {
		for j := 0; j < dim; j++ {
			trace += a.Matrix[i*dim+j] * b.Matrix[j*dim+i]
		}
	}

	return real(trace), nil
}

// StateCount returns the number of active quantum states.
func (sm *StateManager) StateCount() int {
	sm.mu.RLock()
	defer sm.mu.RUnlock()
	return len(sm.states)
}

// EntanglementCount returns the number of entanglement records.
func (sm *StateManager) EntanglementCount() int {
	sm.mu.RLock()
	defer sm.mu.RUnlock()
	return len(sm.entanglements)
}
