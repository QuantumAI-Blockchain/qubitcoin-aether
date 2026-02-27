package quantum

import (
	"fmt"
	"math/big"
)

// MemoryAccessor abstracts the EVM memory for opcodes that read from memory.
// This avoids a circular import between evm and quantum packages.
type MemoryAccessor interface {
	Get(offset, size uint64) []byte
	Resize(size uint64) uint64
}

// Handler executes quantum opcodes (0xF0-0xF9) and AGI opcodes (0xFA-0xFB)
// within the QVM. It bridges the EVM execution context with the quantum
// state manager and the Aether Tree AGI engine.
type Handler struct {
	States *StateManager
	AGI    *AGIHandler
}

// NewHandler creates a quantum opcode handler with AGI support.
func NewHandler() *Handler {
	return &Handler{
		States: NewStateManager(),
		AGI:    NewAGIHandler(),
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
		return h.opQBridgeEntangle(stack)
	case QBRIDGE_VERIFY:
		return h.opQBridgeVerify(stack)

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
	if nQubits == 0 || nQubits > 16 {
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
// Stub implementation — full compliance engine in pkg/compliance.
func (h *Handler) opQCompliance(stack StackAccessor, caller [20]byte) error {
	checkTypeVal, err := stack.Pop()
	if err != nil {
		return err
	}
	_ = checkTypeVal // Will be used by compliance engine
	_ = caller

	// Stub: return compliant (1) — real impl queries compliance engine
	return stack.Push(big.NewInt(1))
}

// opQRisk queries SUSY risk score for an address.
// Stack: [address] → [riskScore (0-10000, scaled by 100)]
func (h *Handler) opQRisk(stack StackAccessor) error {
	_, err := stack.Pop() // address
	if err != nil {
		return err
	}

	// Stub: return low risk (100 = 1.00)
	return stack.PushUint64(100)
}

// opQRiskSystemic queries systemic risk via SUSY contagion model.
// Stack: [] → [systemicRisk (0-10000)]
func (h *Handler) opQRiskSystemic(stack StackAccessor) error {
	// Stub: return low systemic risk
	return stack.PushUint64(50)
}

// opQBridgeEntangle creates cross-chain quantum entanglement.
// Stack: [targetChainID, stateID] → [bridgeEntanglementID]
func (h *Handler) opQBridgeEntangle(stack StackAccessor) error {
	_, err := stack.Pop() // targetChainID
	if err != nil {
		return err
	}
	_, err = stack.Pop() // stateID
	if err != nil {
		return err
	}

	// Stub: return placeholder bridge entanglement ID
	return stack.PushUint64(0)
}

// opQBridgeVerify verifies a cross-chain bridge proof.
// Stack: [proofHash, sourceChainID] → [valid (1/0)]
func (h *Handler) opQBridgeVerify(stack StackAccessor) error {
	_, err := stack.Pop() // proofHash
	if err != nil {
		return err
	}
	_, err = stack.Pop() // sourceChainID
	if err != nil {
		return err
	}

	// Stub: return valid (1)
	return stack.Push(big.NewInt(1))
}
