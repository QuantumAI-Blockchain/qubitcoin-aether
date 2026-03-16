package quantum

import (
	"crypto/hmac"
	"crypto/sha256"
	"encoding/binary"
	"fmt"
	"math/big"
	"sync"
)

// MemoryAccessor abstracts the EVM memory for opcodes that read from memory.
// This avoids a circular import between evm and quantum packages.
// Signatures match evm.Memory: Get and Resize return errors for out-of-bounds
// or max-size violations.
type MemoryAccessor interface {
	Get(offset, size uint64) ([]byte, error)
	Resize(size uint64) (uint64, error)
}

// ComplianceOracle provides compliance/risk data to quantum opcodes.
// When nil, opcodes return safe defaults (compliant=1, low risk).
type ComplianceOracle interface {
	// CheckCompliance returns 1 if compliant, 0 if not.
	CheckCompliance(caller [20]byte, checkType uint64) uint64
	// GetRiskScore returns risk score (0-10000, scaled by 100).
	GetRiskScore(addr [20]byte) uint64
	// GetSystemicRisk returns systemic risk (0-10000).
	GetSystemicRisk() uint64
}

// BridgeEntanglementRecord tracks a cross-chain entanglement created by QBRIDGE_ENTANGLE.
type BridgeEntanglementRecord struct {
	ID            uint64
	SourceChainID uint64
	TargetChainID uint64
	CallerAddr    [20]byte
	StateID       uint64
	ProofHash     [32]byte // HMAC-SHA256 derived deterministic proof
}

// BridgeRegistry manages cross-chain bridge entanglement records.
type BridgeRegistry struct {
	mu      sync.RWMutex
	records map[uint64]*BridgeEntanglementRecord
	nextID  uint64
}

// NewBridgeRegistry creates a new empty bridge registry.
func NewBridgeRegistry() *BridgeRegistry {
	return &BridgeRegistry{
		records: make(map[uint64]*BridgeEntanglementRecord),
		nextID:  1,
	}
}

// Handler executes quantum opcodes (0xC0-0xDE) and AGI opcodes (0xC2-0xC3)
// within the QVM. It bridges the EVM execution context with the quantum
// state manager and the Aether Tree AGI engine.
type Handler struct {
	States     *StateManager
	AGI        *AGIHandler
	Compliance ComplianceOracle // nil → safe defaults
	Bridge     *BridgeRegistry
}

// NewHandler creates a quantum opcode handler with AGI support.
func NewHandler() *Handler {
	return &Handler{
		States: NewStateManager(),
		AGI:    NewAGIHandler(),
		Bridge: NewBridgeRegistry(),
	}
}

// StackAccessor abstracts the EVM stack for quantum opcodes.
// This avoids a circular import between evm and quantum packages.
type StackAccessor interface {
	Pop() (*big.Int, error)
	Push(val *big.Int) error
	PushUint64(val uint64) error
}

// GasConsumer abstracts gas accounting.
type GasConsumer interface {
	UseGas(amount uint64) bool
}

// Execute dispatches a quantum or AGI opcode.
// Returns an error if the opcode fails.
func (h *Handler) Execute(
	op QuantumOpcode,
	stack StackAccessor,
	gas GasConsumer,
	caller [20]byte,
	blockSeed [32]byte,
) error {
	return h.ExecuteWithMemory(op, stack, gas, caller, blockSeed, nil)
}

// ExecuteWithMemory dispatches a quantum or AGI opcode with memory access.
// The memory parameter is required for QREASON (reads query from memory)
// and may be nil for opcodes that do not require memory access.
// Returns an error if the opcode fails.
func (h *Handler) ExecuteWithMemory(
	op QuantumOpcode,
	stack StackAccessor,
	gas GasConsumer,
	caller [20]byte,
	blockSeed [32]byte,
	memory MemoryAccessor,
) error {
	// Charge base gas
	baseCost, ok := QuantumGasCost[op]
	if !ok {
		return fmt.Errorf("unknown quantum opcode: 0x%02x", byte(op))
	}
	if !gas.UseGas(baseCost) {
		return fmt.Errorf("out of gas: quantum opcode 0x%02x costs %d", byte(op), baseCost)
	}

	switch op {
	case QCREATE:
		return h.opQCreate(stack, gas, caller)
	case QMEASURE:
		return h.opQMeasure(stack, blockSeed)
	case QENTANGLE:
		return h.opQEntangle(stack)
	case QGATE:
		return h.opQGate(stack)
	case QVERIFY:
		return h.opQVerify(stack)
	case QCOMPLIANCE:
		return h.opQCompliance(stack, caller)
	case QRISK:
		return h.opQRisk(stack)
	case QRISK_SYSTEMIC:
		return h.opQRiskSystemic(stack)
	case QBRIDGE_ENTANGLE:
		return h.opQBridgeEntangle(stack, caller, blockSeed)
	case QBRIDGE_VERIFY:
		return h.opQBridgeVerify(stack)

	// Extended quantum opcodes
	case QSUPERPOSE:
		return h.opQSuperpose(stack)
	case QVQE:
		return h.opQVQE(stack, gas, blockSeed)
	case QHAMILTONIAN:
		return h.opQHamiltonian(stack, blockSeed)
	case QENERGY:
		return h.opQEnergy(stack)
	case QPROOF:
		return h.opQProof(stack, blockSeed)
	case QFIDELITY:
		return h.opQFidelity(stack)
	case QDILITHIUM:
		return h.opQDilithium(stack, memory)

	// AGI opcodes
	case QREASON:
		return h.AGI.OpQReason(stack, gas, memory)
	case QPHI:
		return h.AGI.OpQPhi(stack)

	default:
		return fmt.Errorf("unimplemented quantum opcode: 0x%02x", byte(op))
	}
}

// opQCreate creates a new quantum state.
// Stack: [nQubits] → [stateID]
// Dynamic gas: 5000 * 2^nQubits (exponential in qubit count).
func (h *Handler) opQCreate(stack StackAccessor, gas GasConsumer, owner [20]byte) error {
	nQubitsVal, err := stack.Pop()
	if err != nil {
		return err
	}
	nQubits := uint8(nQubitsVal.Uint64())
	if nQubits == 0 || nQubits > MaxQubits {
		return stack.Push(big.NewInt(0)) // failure: push 0
	}

	// Dynamic gas: 5000 * 2^n
	dynamicCost := uint64(5000) * (1 << nQubits)
	if !gas.UseGas(dynamicCost) {
		return fmt.Errorf("out of gas: QCREATE dynamic cost %d for %d qubits", dynamicCost, nQubits)
	}

	id, err := h.States.CreateState(nQubits, owner)
	if err != nil {
		return stack.Push(big.NewInt(0))
	}

	return stack.PushUint64(id)
}

// opQMeasure measures a quantum state, collapsing it.
// Stack: [stateID] → [outcome]
func (h *Handler) opQMeasure(stack StackAccessor, blockSeed [32]byte) error {
	idVal, err := stack.Pop()
	if err != nil {
		return err
	}
	id := idVal.Uint64()

	outcome, err := h.States.MeasureState(id, blockSeed)
	if err != nil {
		return stack.Push(big.NewInt(0))
	}

	return stack.PushUint64(outcome)
}

// opQEntangle creates an entangled pair between two quantum states.
// Stack: [stateA, stateB] → [entanglementID]
func (h *Handler) opQEntangle(stack StackAccessor) error {
	aVal, err := stack.Pop()
	if err != nil {
		return err
	}
	bVal, err := stack.Pop()
	if err != nil {
		return err
	}

	entID, err := h.States.Entangle(aVal.Uint64(), bVal.Uint64())
	if err != nil {
		return stack.Push(big.NewInt(0))
	}

	return stack.PushUint64(entID)
}

// opQGate applies a quantum gate to a state.
// Stack: [gateType, stateID, qubitIdx, (param if parameterized)] → [success]
func (h *Handler) opQGate(stack StackAccessor) error {
	gateTypeVal, err := stack.Pop()
	if err != nil {
		return err
	}
	stateIDVal, err := stack.Pop()
	if err != nil {
		return err
	}
	qubitIdxVal, err := stack.Pop()
	if err != nil {
		return err
	}

	gateType := GateType(gateTypeVal.Uint64())
	stateID := stateIDVal.Uint64()
	qubitIdx := uint8(qubitIdxVal.Uint64())

	var theta float64
	if gateType.IsParameterized() {
		paramVal, pErr := stack.Pop()
		if pErr != nil {
			return pErr
		}
		// Parameter is scaled by 10^18 (fixed-point)
		theta = float64(paramVal.Int64()) / 1e18
	}

	state, err := h.States.GetState(stateID)
	if err != nil {
		return stack.Push(big.NewInt(0))
	}

	if gateType.IsTwoQubit() {
		// For CNOT: qubitIdx is control, need target from stack
		targetVal, tErr := stack.Pop()
		if tErr != nil {
			return tErr
		}
		target := uint8(targetVal.Uint64())
		err = ApplyCNOT(state, qubitIdx, target)
	} else {
		err = ApplyGate(state, gateType, qubitIdx, theta)
	}

	if err != nil {
		return stack.Push(big.NewInt(0))
	}
	return stack.Push(big.NewInt(1))
}

// opQVerify verifies a quantum state (trace=1, positive semi-definite).
// Stack: [stateID] → [valid (1/0)]
func (h *Handler) opQVerify(stack StackAccessor) error {
	idVal, err := stack.Pop()
	if err != nil {
		return err
	}

	valid, err := h.States.VerifyState(idVal.Uint64())
	if err != nil || !valid {
		return stack.Push(big.NewInt(0))
	}
	return stack.Push(big.NewInt(1))
}

// opQCompliance checks KYC/AML/sanctions compliance for the caller.
// Stack: [checkType] → [compliant (1/0)]
// checkType: 0=KYC, 1=AML, 2=Sanctions, 3=Full
// Delegates to ComplianceOracle if wired; returns compliant (1) otherwise.
func (h *Handler) opQCompliance(stack StackAccessor, caller [20]byte) error {
	checkTypeVal, err := stack.Pop()
	if err != nil {
		return err
	}

	if h.Compliance != nil {
		result := h.Compliance.CheckCompliance(caller, checkTypeVal.Uint64())
		return stack.PushUint64(result)
	}
	// Default: compliant (1) when no compliance engine wired
	return stack.Push(big.NewInt(1))
}

// opQRisk queries SUSY risk score for an address.
// Stack: [address] → [riskScore (0-10000, scaled by 100)]
// Delegates to ComplianceOracle if wired; returns low risk (100) otherwise.
func (h *Handler) opQRisk(stack StackAccessor) error {
	addrVal, err := stack.Pop()
	if err != nil {
		return err
	}

	if h.Compliance != nil {
		var addr [20]byte
		addrBytes := addrVal.Bytes()
		if len(addrBytes) > 20 {
			addrBytes = addrBytes[len(addrBytes)-20:]
		}
		copy(addr[20-len(addrBytes):], addrBytes)
		result := h.Compliance.GetRiskScore(addr)
		return stack.PushUint64(result)
	}
	// Default: low risk (100 = 1.00)
	return stack.PushUint64(100)
}

// opQRiskSystemic queries systemic risk via SUSY contagion model.
// Stack: [] → [systemicRisk (0-10000)]
// Delegates to ComplianceOracle if wired; returns low risk (50) otherwise.
func (h *Handler) opQRiskSystemic(stack StackAccessor) error {
	if h.Compliance != nil {
		result := h.Compliance.GetSystemicRisk()
		return stack.PushUint64(result)
	}
	// Default: low systemic risk
	return stack.PushUint64(50)
}

// opQBridgeEntangle creates a cross-chain entanglement record.
//
// Stack: [targetChainID, stateID] → [bridgeEntanglementID]
//
// The entanglement ID is derived deterministically using HMAC-SHA256
// over the caller address, target chain ID, state ID, and block seed.
// This ensures all validators produce the same entanglement ID for
// the same inputs within the same block.
func (h *Handler) opQBridgeEntangle(stack StackAccessor, caller [20]byte, blockSeed [32]byte) error {
	targetChainIDVal, err := stack.Pop()
	if err != nil {
		return err
	}
	stateIDVal, err := stack.Pop()
	if err != nil {
		return err
	}

	targetChainID := targetChainIDVal.Uint64()
	stateID := stateIDVal.Uint64()

	// Derive a deterministic entanglement ID using HMAC-SHA256
	// Key: blockSeed (ensures uniqueness per block)
	// Message: caller ++ targetChainID ++ stateID
	mac := hmac.New(sha256.New, blockSeed[:])
	mac.Write(caller[:])
	var buf [8]byte
	binary.BigEndian.PutUint64(buf[:], targetChainID)
	mac.Write(buf[:])
	binary.BigEndian.PutUint64(buf[:], stateID)
	mac.Write(buf[:])
	proofHash := mac.Sum(nil)

	var proofHashArr [32]byte
	copy(proofHashArr[:], proofHash)

	// Create and store the bridge entanglement record
	h.Bridge.mu.Lock()
	id := h.Bridge.nextID
	h.Bridge.records[id] = &BridgeEntanglementRecord{
		ID:            id,
		SourceChainID: 3303, // QBC mainnet
		TargetChainID: targetChainID,
		CallerAddr:    caller,
		StateID:       stateID,
		ProofHash:     proofHashArr,
	}
	h.Bridge.nextID++
	h.Bridge.mu.Unlock()

	return stack.PushUint64(id)
}

// opQBridgeVerify verifies a cross-chain bridge proof.
//
// Stack: [proofHash, bridgeEntanglementID] → [valid (1/0)]
//
// Verification checks that:
//  1. An entanglement record exists with the given ID
//  2. The provided proof hash matches the stored proof hash
//
// Returns 1 if valid, 0 if the entanglement does not exist or proof mismatches.
func (h *Handler) opQBridgeVerify(stack StackAccessor) error {
	proofHashVal, err := stack.Pop()
	if err != nil {
		return err
	}
	entIDVal, err := stack.Pop()
	if err != nil {
		return err
	}

	entID := entIDVal.Uint64()

	// Extract proof hash from stack value
	var providedHash [32]byte
	proofBytes := proofHashVal.Bytes()
	if len(proofBytes) > 32 {
		proofBytes = proofBytes[len(proofBytes)-32:]
	}
	copy(providedHash[32-len(proofBytes):], proofBytes)

	// Look up the entanglement record
	h.Bridge.mu.RLock()
	record, ok := h.Bridge.records[entID]
	h.Bridge.mu.RUnlock()

	if !ok {
		// Entanglement record not found
		return stack.Push(big.NewInt(0))
	}

	// Verify the proof hash matches
	if record.ProofHash == providedHash {
		return stack.Push(big.NewInt(1))
	}

	return stack.Push(big.NewInt(0))
}

// opQSuperpose puts a qubit into equal superposition (applies Hadamard gate).
// Stack: [stateID, qubitIdx] → [success (1/0)]
func (h *Handler) opQSuperpose(stack StackAccessor) error {
	stateIDVal, err := stack.Pop()
	if err != nil {
		return err
	}
	qubitIdxVal, err := stack.Pop()
	if err != nil {
		return err
	}

	state, err := h.States.GetState(stateIDVal.Uint64())
	if err != nil {
		return stack.Push(big.NewInt(0))
	}

	err = ApplyGate(state, GateH, uint8(qubitIdxVal.Uint64()), 0)
	if err != nil {
		return stack.Push(big.NewInt(0))
	}
	return stack.Push(big.NewInt(1))
}

// opQVQE executes a single VQE optimization step on a quantum state.
// Stack: [stateID] → [energyScaled (fixed-point, 1e18)]
// Uses the block seed to derive a deterministic Hamiltonian and evaluates
// the energy expectation value of the current state against it.
func (h *Handler) opQVQE(stack StackAccessor, gas GasConsumer, blockSeed [32]byte) error {
	stateIDVal, err := stack.Pop()
	if err != nil {
		return err
	}

	state, err := h.States.GetState(stateIDVal.Uint64())
	if err != nil {
		return stack.Push(big.NewInt(0))
	}

	// Dynamic gas: VQE scales with qubit count
	dynamicCost := uint64(10000) * (1 << state.NQubits)
	if !gas.UseGas(dynamicCost) {
		return fmt.Errorf("out of gas: QVQE dynamic cost %d for %d qubits", dynamicCost, state.NQubits)
	}

	// Compute energy expectation using HMAC-derived Hamiltonian diagonal
	mac := hmac.New(sha256.New, blockSeed[:])
	mac.Write([]byte("vqe-hamiltonian"))
	hBytes := mac.Sum(nil)

	dim := 1 << state.NQubits
	energy := 0.0
	for i := 0; i < dim && i < len(hBytes); i++ {
		// Diagonal Hamiltonian element from hash byte, scaled to [-1, 1]
		hVal := (float64(hBytes[i%len(hBytes)]) - 128.0) / 128.0
		// Probability = diagonal of density matrix (real part)
		idx := i*dim + i
		if idx < len(state.Matrix) {
			energy += hVal * real(state.Matrix[idx])
		}
	}

	// Return energy as fixed-point (scaled by 1e18)
	energyScaled := int64(energy * 1e18)
	return stack.Push(big.NewInt(energyScaled))
}

// opQHamiltonian generates a deterministic Hamiltonian seed from the block seed.
// Stack: [nQubits] → [hamiltonianHash]
// The hash can be used by contracts to verify Hamiltonian derivation.
func (h *Handler) opQHamiltonian(stack StackAccessor, blockSeed [32]byte) error {
	nQubitsVal, err := stack.Pop()
	if err != nil {
		return err
	}

	nQubits := nQubitsVal.Uint64()
	if nQubits == 0 || nQubits > uint64(MaxQubits) {
		return stack.Push(big.NewInt(0))
	}

	// Derive deterministic Hamiltonian hash from block seed + qubit count
	mac := hmac.New(sha256.New, blockSeed[:])
	mac.Write([]byte("hamiltonian"))
	var buf [8]byte
	binary.BigEndian.PutUint64(buf[:], nQubits)
	mac.Write(buf[:])
	hash := mac.Sum(nil)

	result := new(big.Int).SetBytes(hash)
	return stack.Push(result)
}

// opQEnergy computes the energy expectation value of a quantum state.
// Stack: [stateID] → [energyScaled (fixed-point, 1e18)]
// Returns the trace of the density matrix diagonal (sum of probabilities
// weighted by basis state index), providing a deterministic energy metric.
func (h *Handler) opQEnergy(stack StackAccessor) error {
	stateIDVal, err := stack.Pop()
	if err != nil {
		return err
	}

	state, err := h.States.GetState(stateIDVal.Uint64())
	if err != nil {
		return stack.Push(big.NewInt(0))
	}

	// Compute energy as weighted sum of diagonal density matrix elements
	dim := 1 << state.NQubits
	energy := 0.0
	for i := 0; i < dim; i++ {
		idx := i*dim + i
		if idx < len(state.Matrix) {
			// Weight by basis state index (normalized)
			weight := float64(i) / float64(dim)
			energy += weight * real(state.Matrix[idx])
		}
	}

	energyScaled := int64(energy * 1e18)
	return stack.Push(big.NewInt(energyScaled))
}

// opQProof validates a quantum computation proof.
// Stack: [stateID, expectedHash] → [valid (1/0)]
// Computes SHA-256 over the density matrix and compares with expected hash.
func (h *Handler) opQProof(stack StackAccessor, blockSeed [32]byte) error {
	stateIDVal, err := stack.Pop()
	if err != nil {
		return err
	}
	expectedHashVal, err := stack.Pop()
	if err != nil {
		return err
	}

	state, err := h.States.GetState(stateIDVal.Uint64())
	if err != nil {
		return stack.Push(big.NewInt(0))
	}

	// Hash the density matrix to produce a proof
	hasher := sha256.New()
	hasher.Write(blockSeed[:])
	for _, c := range state.Matrix {
		var buf [16]byte
		binary.BigEndian.PutUint64(buf[:8], uint64(real(c)*1e18))
		binary.BigEndian.PutUint64(buf[8:], uint64(imag(c)*1e18))
		hasher.Write(buf[:])
	}
	proofHash := hasher.Sum(nil)

	// Compare with expected hash
	var expected [32]byte
	expBytes := expectedHashVal.Bytes()
	if len(expBytes) > 32 {
		expBytes = expBytes[len(expBytes)-32:]
	}
	copy(expected[32-len(expBytes):], expBytes)

	var computed [32]byte
	copy(computed[:], proofHash)

	if computed == expected {
		return stack.Push(big.NewInt(1))
	}
	return stack.Push(big.NewInt(0))
}

// opQFidelity computes the fidelity between two quantum states.
// Stack: [stateA, stateB] → [fidelityScaled (0-1e18)]
// Fidelity measures how similar two quantum states are.
// Returns Tr(rho_A * rho_B) scaled by 1e18.
func (h *Handler) opQFidelity(stack StackAccessor) error {
	aVal, err := stack.Pop()
	if err != nil {
		return err
	}
	bVal, err := stack.Pop()
	if err != nil {
		return err
	}

	stateA, err := h.States.GetState(aVal.Uint64())
	if err != nil {
		return stack.Push(big.NewInt(0))
	}
	stateB, err := h.States.GetState(bVal.Uint64())
	if err != nil {
		return stack.Push(big.NewInt(0))
	}

	if stateA.NQubits != stateB.NQubits {
		return stack.Push(big.NewInt(0))
	}

	// Compute Tr(rho_A * rho_B) for density matrices
	dim := 1 << stateA.NQubits
	fidelity := 0.0
	for i := 0; i < dim; i++ {
		for j := 0; j < dim; j++ {
			idxA := i*dim + j
			idxB := j*dim + i
			if idxA < len(stateA.Matrix) && idxB < len(stateB.Matrix) {
				prod := stateA.Matrix[idxA] * stateB.Matrix[idxB]
				fidelity += real(prod)
			}
		}
	}

	// Clamp to [0, 1]
	if fidelity < 0 {
		fidelity = 0
	}
	if fidelity > 1 {
		fidelity = 1
	}

	fidelityScaled := int64(fidelity * 1e18)
	return stack.Push(big.NewInt(fidelityScaled))
}

// opQDilithium verifies a Dilithium post-quantum signature.
// Stack: [msgOffset, msgLen, sigOffset, sigLen, pubkeyOffset, pubkeyLen] → [valid (1/0)]
// Reads message, signature, and public key from EVM memory and performs
// SHA-256 based verification (simplified for EVM context — full Dilithium5
// verification happens at the L1 consensus layer).
func (h *Handler) opQDilithium(stack StackAccessor, memory MemoryAccessor) error {
	msgOffVal, err := stack.Pop()
	if err != nil {
		return err
	}
	msgLenVal, err := stack.Pop()
	if err != nil {
		return err
	}
	sigOffVal, err := stack.Pop()
	if err != nil {
		return err
	}
	sigLenVal, err := stack.Pop()
	if err != nil {
		return err
	}
	pubOffVal, err := stack.Pop()
	if err != nil {
		return err
	}
	pubLenVal, err := stack.Pop()
	if err != nil {
		return err
	}

	// Read data from memory
	msg, err := memory.Get(msgOffVal.Uint64(), msgLenVal.Uint64())
	if err != nil {
		return stack.Push(big.NewInt(0))
	}
	sig, err := memory.Get(sigOffVal.Uint64(), sigLenVal.Uint64())
	if err != nil {
		return stack.Push(big.NewInt(0))
	}
	pubkey, err := memory.Get(pubOffVal.Uint64(), pubLenVal.Uint64())
	if err != nil {
		return stack.Push(big.NewInt(0))
	}

	// Simplified verification: HMAC-SHA256(pubkey, msg) prefix matches sig
	// Full Dilithium5 verification is performed at L1 consensus level.
	// This opcode provides a lightweight on-chain check for smart contracts.
	mac := hmac.New(sha256.New, pubkey)
	mac.Write(msg)
	expected := mac.Sum(nil)

	// Check if signature starts with the expected HMAC prefix
	if len(sig) >= 32 {
		var expArr, sigArr [32]byte
		copy(expArr[:], expected[:32])
		copy(sigArr[:], sig[:32])
		if expArr == sigArr {
			return stack.Push(big.NewInt(1))
		}
	}

	return stack.Push(big.NewInt(0))
}
