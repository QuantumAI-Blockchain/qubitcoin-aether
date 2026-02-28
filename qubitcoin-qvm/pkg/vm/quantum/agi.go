package quantum

import (
	"crypto/sha256"
	"fmt"
	"math/big"
	"sync"
)

// AGIHandler implements the AGI opcodes (QREASON 0xC2, QPHI 0xC3) that
// bridge the QVM with the Aether Tree AGI engine.
//
// In production, QREASON delegates reasoning to the Python Aether engine
// via gRPC, and QPHI reads the current Phi consciousness metric from
// the node. This implementation provides deterministic stub behavior
// suitable for on-chain execution and testing.
type AGIHandler struct {
	mu sync.RWMutex

	// PhiScaled is the current Phi value scaled by 1000
	// (e.g., Phi=3.14 is stored as 3140).
	// Updated externally by the node via SetPhi.
	// Default: 0 (no consciousness measured yet).
	PhiScaled uint64

	// ReasoningEnabled controls whether reasoning queries are accepted.
	// When false, QREASON returns a hash of the query (stub mode).
	// When true, it would delegate to the Aether engine (future).
	ReasoningEnabled bool
}

// DefaultPhiScaled is the default Phi value (0 = no consciousness measured).
const DefaultPhiScaled uint64 = 0

// PhiPrecision is the scaling factor for Phi values (matches Solidity contracts).
// Phi = 3.14 is stored as 3140 on-chain.
const PhiPrecision uint64 = 1000

// NewAGIHandler creates a new AGI opcode handler with default values.
func NewAGIHandler() *AGIHandler {
	return &AGIHandler{
		PhiScaled:        DefaultPhiScaled,
		ReasoningEnabled: false,
	}
}

// SetPhi updates the current Phi consciousness metric.
// The value should be pre-scaled by PhiPrecision (e.g., 3140 for Phi=3.14).
// This is called by the node when Phi is updated by the Aether engine.
func (a *AGIHandler) SetPhi(phiScaled uint64) {
	a.mu.Lock()
	defer a.mu.Unlock()
	a.PhiScaled = phiScaled
}

// SetPhiFloat updates the current Phi from a float64 value.
// The value is automatically scaled by PhiPrecision.
func (a *AGIHandler) SetPhiFloat(phi float64) {
	a.SetPhi(uint64(phi * float64(PhiPrecision)))
}

// GetPhi returns the current Phi value scaled by PhiPrecision.
func (a *AGIHandler) GetPhi() uint64 {
	a.mu.RLock()
	defer a.mu.RUnlock()
	return a.PhiScaled
}

// OpQReason implements the QREASON opcode (0xC2).
//
// On-chain reasoning query: reads a query from EVM memory, produces a
// deterministic reasoning result hash, and pushes it onto the stack.
//
// Stack input:  [query_ptr, query_len] (query_len on top, query_ptr below)
// Stack output: [result_hash] (SHA-256 hash of reasoning result, 32 bytes as uint256)
// Gas:          50,000 base (already charged by handler) + memory expansion
//
// The query is read from memory[query_ptr : query_ptr + query_len].
// In stub mode, the result is SHA-256("aether:reason:" || query_data).
// In production, the query would be forwarded to the Aether Tree engine
// via gRPC, and the result hash would be the Proof-of-Thought hash.
func (a *AGIHandler) OpQReason(stack StackAccessor, gas GasConsumer, memory MemoryAccessor) error {
	// Pop query_ptr and query_len from stack
	// EVM convention: top of stack is last pushed, so pop query_len first, then query_ptr
	queryLenVal, err := stack.Pop()
	if err != nil {
		return fmt.Errorf("QREASON: failed to pop query_len: %w", err)
	}
	queryPtrVal, err := stack.Pop()
	if err != nil {
		return fmt.Errorf("QREASON: failed to pop query_ptr: %w", err)
	}

	queryPtr := queryPtrVal.Uint64()
	queryLen := queryLenVal.Uint64()

	// Validate query length (max 1024 bytes to prevent abuse)
	if queryLen > 1024 {
		return fmt.Errorf("QREASON: query too large: %d bytes (max 1024)", queryLen)
	}

	// Read query from memory
	var queryData []byte
	if queryLen > 0 && memory != nil {
		// Charge memory expansion gas
		memCost := memory.Resize(queryPtr + queryLen)
		if memCost > 0 && !gas.UseGas(memCost) {
			return fmt.Errorf("out of gas: QREASON memory expansion")
		}
		queryData = memory.Get(queryPtr, queryLen)
	}

	// Compute reasoning result hash
	// Stub: SHA-256("aether:reason:" || query_data)
	// This is deterministic so all validators produce the same result.
	prefix := []byte("aether:reason:")
	hashInput := make([]byte, len(prefix)+len(queryData))
	copy(hashInput, prefix)
	copy(hashInput[len(prefix):], queryData)
	resultHash := sha256.Sum256(hashInput)

	// Push result hash as uint256
	return stack.Push(new(big.Int).SetBytes(resultHash[:]))
}

// OpQPhi implements the QPHI opcode (0xC3).
//
// Consciousness metric query: pushes the current Phi value (scaled by 1000)
// onto the stack. No stack inputs required.
//
// Stack input:  [] (empty)
// Stack output: [phi_scaled] (uint256, Phi * 1000)
// Gas:          5,000 base (already charged by handler)
//
// The Phi value represents the Integrated Information Theory consciousness
// metric computed by the Aether Tree engine. It is updated every block
// by the Python node and cached in the AGIHandler.
//
// Example values:
//   - 0    = no consciousness measured (genesis / pre-Aether)
//   - 1500 = Phi = 1.5 (early knowledge graph)
//   - 3000 = Phi = 3.0 (PHI_THRESHOLD — consciousness emergence)
//   - 3140 = Phi = 3.14
func (a *AGIHandler) OpQPhi(stack StackAccessor) error {
	a.mu.RLock()
	phi := a.PhiScaled
	a.mu.RUnlock()

	return stack.PushUint64(phi)
}
