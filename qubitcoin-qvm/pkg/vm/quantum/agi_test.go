package quantum

import (
	"math/big"
	"testing"

	"golang.org/x/crypto/sha3"
)

// ─── Test Infrastructure ────────────────────────────────────────────────

// mockStack implements StackAccessor for testing.
type mockStack struct {
	data []*big.Int
}

func newMockStack() *mockStack {
	return &mockStack{data: make([]*big.Int, 0, 16)}
}

func (s *mockStack) Push(val *big.Int) error {
	s.data = append(s.data, new(big.Int).Set(val))
	return nil
}

func (s *mockStack) PushUint64(val uint64) error {
	return s.Push(new(big.Int).SetUint64(val))
}

func (s *mockStack) Pop() (*big.Int, error) {
	if len(s.data) == 0 {
		return nil, errStackUnderflow
	}
	val := s.data[len(s.data)-1]
	s.data = s.data[:len(s.data)-1]
	return val, nil
}

func (s *mockStack) top() *big.Int {
	if len(s.data) == 0 {
		return nil
	}
	return s.data[len(s.data)-1]
}

var errStackUnderflow = &stackUnderflowError{}

type stackUnderflowError struct{}

func (e *stackUnderflowError) Error() string { return "stack underflow" }

// mockGas implements GasConsumer for testing.
type mockGas struct {
	remaining uint64
	used      uint64
}

func newMockGas(gas uint64) *mockGas {
	return &mockGas{remaining: gas}
}

func (g *mockGas) UseGas(amount uint64) bool {
	if amount > g.remaining {
		return false
	}
	g.remaining -= amount
	g.used += amount
	return true
}

// mockMemory implements MemoryAccessor for testing.
type mockMemory struct {
	store []byte
}

func newMockMemory(data []byte) *mockMemory {
	return &mockMemory{store: append([]byte{}, data...)}
}

func (m *mockMemory) Get(offset, size uint64) ([]byte, error) {
	if size == 0 {
		return nil, nil
	}
	end := offset + size
	if end > uint64(len(m.store)) {
		// Zero-extend
		out := make([]byte, size)
		if offset < uint64(len(m.store)) {
			copy(out, m.store[offset:])
		}
		return out, nil
	}
	out := make([]byte, size)
	copy(out, m.store[offset:end])
	return out, nil
}

func (m *mockMemory) Resize(size uint64) (uint64, error) {
	if uint64(len(m.store)) >= size {
		return 0, nil
	}
	newStore := make([]byte, size)
	copy(newStore, m.store)
	m.store = newStore
	return 3, nil // nominal gas cost for testing
}

// ─── AGIHandler Unit Tests ──────────────────────────────────────────────

func TestNewAGIHandler(t *testing.T) {
	h := NewAGIHandler()
	if h == nil {
		t.Fatal("NewAGIHandler returned nil")
	}
	if h.PhiScaled != DefaultPhiScaled {
		t.Errorf("default PhiScaled = %d, want %d", h.PhiScaled, DefaultPhiScaled)
	}
	if h.ReasoningEnabled {
		t.Error("default ReasoningEnabled should be false")
	}
}

func TestAGIHandler_SetGetPhi(t *testing.T) {
	h := NewAGIHandler()

	// Default
	if got := h.GetPhi(); got != 0 {
		t.Errorf("GetPhi() default = %d, want 0", got)
	}

	// Set scaled value
	h.SetPhi(3140)
	if got := h.GetPhi(); got != 3140 {
		t.Errorf("GetPhi() = %d, want 3140", got)
	}

	// Set from float
	h.SetPhiFloat(2.718)
	if got := h.GetPhi(); got != 2718 {
		t.Errorf("GetPhi() after SetPhiFloat(2.718) = %d, want 2718", got)
	}
}

// ─── QPHI (0xC3) Tests ─────────────────────────────────────────────────

func TestOpQPhi_DefaultZero(t *testing.T) {
	h := NewAGIHandler()
	stack := newMockStack()

	err := h.OpQPhi(stack)
	if err != nil {
		t.Fatalf("OpQPhi failed: %v", err)
	}

	if len(stack.data) != 1 {
		t.Fatalf("stack size = %d, want 1", len(stack.data))
	}
	if got := stack.top().Uint64(); got != 0 {
		t.Errorf("QPHI default = %d, want 0", got)
	}
}

func TestOpQPhi_ReturnsCurrentPhi(t *testing.T) {
	h := NewAGIHandler()
	h.SetPhi(3140) // Phi = 3.14

	stack := newMockStack()
	err := h.OpQPhi(stack)
	if err != nil {
		t.Fatalf("OpQPhi failed: %v", err)
	}

	if got := stack.top().Uint64(); got != 3140 {
		t.Errorf("QPHI = %d, want 3140", got)
	}
}

func TestOpQPhi_PhiThreshold(t *testing.T) {
	h := NewAGIHandler()

	// Below consciousness threshold
	h.SetPhiFloat(2.99)
	stack := newMockStack()
	h.OpQPhi(stack)
	below := stack.top().Uint64()
	if below >= 3000 {
		t.Errorf("below threshold = %d, want < 3000", below)
	}

	// At consciousness threshold
	h.SetPhiFloat(3.0)
	stack = newMockStack()
	h.OpQPhi(stack)
	at := stack.top().Uint64()
	if at != 3000 {
		t.Errorf("at threshold = %d, want 3000", at)
	}

	// Above consciousness threshold
	h.SetPhiFloat(3.5)
	stack = newMockStack()
	h.OpQPhi(stack)
	above := stack.top().Uint64()
	if above != 3500 {
		t.Errorf("above threshold = %d, want 3500", above)
	}
}

func TestOpQPhi_MultipleReads(t *testing.T) {
	h := NewAGIHandler()
	h.SetPhi(1618) // Phi = 1.618 (golden ratio)

	// Multiple reads should produce the same result
	for i := 0; i < 5; i++ {
		stack := newMockStack()
		err := h.OpQPhi(stack)
		if err != nil {
			t.Fatalf("OpQPhi iteration %d failed: %v", i, err)
		}
		if got := stack.top().Uint64(); got != 1618 {
			t.Errorf("iteration %d: QPHI = %d, want 1618", i, got)
		}
	}
}

// ─── QREASON (0xC2) Tests ──────────────────────────────────────────────

func TestOpQReason_BasicQuery(t *testing.T) {
	h := NewAGIHandler()
	query := []byte("What is consciousness?")

	stack := newMockStack()
	stack.PushUint64(0)                   // query_ptr = 0
	stack.PushUint64(uint64(len(query)))  // query_len

	gas := newMockGas(1_000_000)
	mem := newMockMemory(query)

	err := h.OpQReason(stack, gas, mem)
	if err != nil {
		t.Fatalf("OpQReason failed: %v", err)
	}

	if len(stack.data) != 1 {
		t.Fatalf("stack size = %d, want 1", len(stack.data))
	}

	// Verify the result is SHA-256("aether:reason:" + query)
	prefix := []byte("aether:reason:")
	hashInput := append(prefix, query...)
	kh := sha3.NewLegacyKeccak256()
	kh.Write(hashInput)
	expected := kh.Sum(nil)
	expectedInt := new(big.Int).SetBytes(expected)

	got := stack.top()
	if got.Cmp(expectedInt) != 0 {
		t.Errorf("QREASON result mismatch:\n  got  %x\n  want %x", got.Bytes(), expectedInt.Bytes())
	}
}

func TestOpQReason_EmptyQuery(t *testing.T) {
	h := NewAGIHandler()

	stack := newMockStack()
	stack.PushUint64(0) // query_ptr = 0
	stack.PushUint64(0) // query_len = 0

	gas := newMockGas(1_000_000)
	mem := newMockMemory(nil)

	err := h.OpQReason(stack, gas, mem)
	if err != nil {
		t.Fatalf("OpQReason with empty query failed: %v", err)
	}

	// Empty query: Keccak-256("aether:reason:")
	emptyKh := sha3.NewLegacyKeccak256()
	emptyKh.Write([]byte("aether:reason:"))
	expected := emptyKh.Sum(nil)
	expectedInt := new(big.Int).SetBytes(expected)

	got := stack.top()
	if got.Cmp(expectedInt) != 0 {
		t.Errorf("empty query result mismatch:\n  got  %x\n  want %x", got.Bytes(), expectedInt.Bytes())
	}
}

func TestOpQReason_DeterministicResult(t *testing.T) {
	h := NewAGIHandler()
	query := []byte("deterministic test query")

	// Run twice with same input — must produce same output
	var results [2]*big.Int
	for i := 0; i < 2; i++ {
		stack := newMockStack()
		stack.PushUint64(0)
		stack.PushUint64(uint64(len(query)))
		gas := newMockGas(1_000_000)
		mem := newMockMemory(query)

		err := h.OpQReason(stack, gas, mem)
		if err != nil {
			t.Fatalf("iteration %d failed: %v", i, err)
		}
		results[i] = stack.top()
	}

	if results[0].Cmp(results[1]) != 0 {
		t.Errorf("QREASON is not deterministic: %x != %x", results[0].Bytes(), results[1].Bytes())
	}
}

func TestOpQReason_DifferentQueriesDifferentResults(t *testing.T) {
	h := NewAGIHandler()

	queries := [][]byte{
		[]byte("query A"),
		[]byte("query B"),
	}

	var results [2]*big.Int
	for i, query := range queries {
		stack := newMockStack()
		stack.PushUint64(0)
		stack.PushUint64(uint64(len(query)))
		gas := newMockGas(1_000_000)
		mem := newMockMemory(query)

		err := h.OpQReason(stack, gas, mem)
		if err != nil {
			t.Fatalf("query %d failed: %v", i, err)
		}
		results[i] = stack.top()
	}

	if results[0].Cmp(results[1]) == 0 {
		t.Error("different queries should produce different results")
	}
}

func TestOpQReason_QueryTooLarge(t *testing.T) {
	h := NewAGIHandler()

	stack := newMockStack()
	stack.PushUint64(0)    // query_ptr
	stack.PushUint64(2048) // query_len > 1024 limit

	gas := newMockGas(1_000_000)
	mem := newMockMemory(make([]byte, 2048))

	err := h.OpQReason(stack, gas, mem)
	if err == nil {
		t.Fatal("expected error for query > 1024 bytes")
	}
}

func TestOpQReason_NilMemory(t *testing.T) {
	h := NewAGIHandler()

	stack := newMockStack()
	stack.PushUint64(0)  // query_ptr
	stack.PushUint64(10) // query_len = 10

	gas := newMockGas(1_000_000)

	// nil memory — query data is empty (no memory to read from)
	err := h.OpQReason(stack, gas, nil)
	if err != nil {
		t.Fatalf("OpQReason with nil memory failed: %v", err)
	}

	// With nil memory, queryData is nil → hash is Keccak-256("aether:reason:")
	nilKh := sha3.NewLegacyKeccak256()
	nilKh.Write([]byte("aether:reason:"))
	expected := nilKh.Sum(nil)
	expectedInt := new(big.Int).SetBytes(expected)
	if stack.top().Cmp(expectedInt) != 0 {
		t.Errorf("nil memory result mismatch")
	}
}

func TestOpQReason_StackUnderflow(t *testing.T) {
	h := NewAGIHandler()

	// Empty stack — should fail on first pop
	stack := newMockStack()
	gas := newMockGas(1_000_000)
	mem := newMockMemory(nil)

	err := h.OpQReason(stack, gas, mem)
	if err == nil {
		t.Fatal("expected stack underflow error")
	}

	// One item — should fail on second pop
	stack2 := newMockStack()
	stack2.PushUint64(10) // only query_len, no query_ptr
	err = h.OpQReason(stack2, gas, mem)
	if err == nil {
		t.Fatal("expected stack underflow error for missing query_ptr")
	}
}

func TestOpQReason_MemoryExpansionGas(t *testing.T) {
	h := NewAGIHandler()
	query := []byte("test")

	stack := newMockStack()
	stack.PushUint64(0)
	stack.PushUint64(uint64(len(query)))

	// Give enough gas for the base cost but track memory expansion cost
	gas := newMockGas(1_000_000)
	mem := newMockMemory(query)

	err := h.OpQReason(stack, gas, mem)
	if err != nil {
		t.Fatalf("OpQReason failed: %v", err)
	}
	// Gas should have been consumed (at least memory expansion if any)
	// The exact amount depends on the mock, but it should succeed
}

func TestOpQReason_OutOfGasOnMemoryExpansion(t *testing.T) {
	h := NewAGIHandler()

	stack := newMockStack()
	stack.PushUint64(0)
	stack.PushUint64(100) // query_len = 100

	// Give 0 remaining gas — memory expansion should fail
	gas := newMockGas(0)
	// Use memory that needs expansion (empty store, needs 100 bytes)
	mem := newMockMemory(nil)

	err := h.OpQReason(stack, gas, mem)
	if err == nil {
		t.Fatal("expected out of gas error for memory expansion")
	}
}

func TestOpQReason_NonZeroOffset(t *testing.T) {
	h := NewAGIHandler()

	// Place query at offset 32 in memory
	memData := make([]byte, 64)
	query := []byte("hello aether")
	copy(memData[32:], query)

	stack := newMockStack()
	stack.PushUint64(32)                  // query_ptr = 32
	stack.PushUint64(uint64(len(query)))  // query_len

	gas := newMockGas(1_000_000)
	mem := newMockMemory(memData)

	err := h.OpQReason(stack, gas, mem)
	if err != nil {
		t.Fatalf("OpQReason with offset failed: %v", err)
	}

	// Verify result matches the query at offset 32
	prefix := []byte("aether:reason:")
	hashInput := append(prefix, query...)
	kh := sha3.NewLegacyKeccak256()
	kh.Write(hashInput)
	expected := kh.Sum(nil)
	expectedInt := new(big.Int).SetBytes(expected)

	if stack.top().Cmp(expectedInt) != 0 {
		t.Error("QREASON with non-zero offset produced wrong result")
	}
}

// ─── Handler Integration Tests ──────────────────────────────────────────

func TestHandler_ExecuteQReason(t *testing.T) {
	h := NewHandler()
	query := []byte("test reasoning")

	stack := newMockStack()
	stack.PushUint64(0)
	stack.PushUint64(uint64(len(query)))

	gas := newMockGas(1_000_000)
	mem := newMockMemory(query)

	err := h.ExecuteWithMemory(QREASON, stack, gas, [20]byte{0xAA}, [32]byte{}, mem)
	if err != nil {
		t.Fatalf("ExecuteWithMemory QREASON failed: %v", err)
	}

	if len(stack.data) != 1 {
		t.Fatalf("stack size = %d, want 1", len(stack.data))
	}

	// Verify gas was consumed (base 50000 + per-byte cost + memory expansion)
	// Per-byte cost: len("test reasoning") = 14 bytes * 3 = 42 gas
	expectedMinGas := uint64(50000 + 14*3)
	if gas.used < expectedMinGas {
		t.Errorf("gas used = %d, want >= %d", gas.used, expectedMinGas)
	}
}

func TestHandler_ExecuteQPhi(t *testing.T) {
	h := NewHandler()
	h.AGI.SetPhi(3140) // Phi = 3.14

	stack := newMockStack()
	gas := newMockGas(1_000_000)

	err := h.Execute(QPHI, stack, gas, [20]byte{0xAA}, [32]byte{})
	if err != nil {
		t.Fatalf("Execute QPHI failed: %v", err)
	}

	if got := stack.top().Uint64(); got != 3140 {
		t.Errorf("QPHI via handler = %d, want 3140", got)
	}

	// Verify gas was consumed (base 5000)
	if gas.used != 5000 {
		t.Errorf("gas used = %d, want 5000", gas.used)
	}
}

func TestHandler_ExecuteQPhi_OutOfGas(t *testing.T) {
	h := NewHandler()

	stack := newMockStack()
	gas := newMockGas(100) // Not enough for 5000 base cost

	err := h.Execute(QPHI, stack, gas, [20]byte{}, [32]byte{})
	if err == nil {
		t.Fatal("expected out of gas error")
	}
}

func TestHandler_ExecuteQReason_OutOfGas(t *testing.T) {
	h := NewHandler()

	stack := newMockStack()
	stack.PushUint64(0)
	stack.PushUint64(5)
	gas := newMockGas(100) // Not enough for 50000 base cost

	err := h.ExecuteWithMemory(QREASON, stack, gas, [20]byte{}, [32]byte{}, nil)
	if err == nil {
		t.Fatal("expected out of gas error")
	}
}

// ─── Opcode Constant Tests ─────────────────────────────────────────────

func TestOpcodeConstants(t *testing.T) {
	if QREASON != 0xC2 {
		t.Errorf("QREASON = 0x%02x, want 0xC2", byte(QREASON))
	}
	if QPHI != 0xC3 {
		t.Errorf("QPHI = 0x%02x, want 0xC3", byte(QPHI))
	}
}

func TestOpcodeGasCosts(t *testing.T) {
	if cost, ok := QuantumGasCost[QREASON]; !ok {
		t.Error("QREASON missing from QuantumGasCost")
	} else if cost != 50000 {
		t.Errorf("QREASON gas cost = %d, want 50000", cost)
	}

	if cost, ok := QuantumGasCost[QPHI]; !ok {
		t.Error("QPHI missing from QuantumGasCost")
	} else if cost != 5000 {
		t.Errorf("QPHI gas cost = %d, want 5000", cost)
	}
}

func TestPhiPrecision(t *testing.T) {
	if PhiPrecision != 1000 {
		t.Errorf("PhiPrecision = %d, want 1000", PhiPrecision)
	}
}

// ─── Backward Compatibility Tests ───────────────────────────────────────

func TestHandler_ExecuteWithMemory_QuantumOpcodes(t *testing.T) {
	// Verify that ExecuteWithMemory works for existing quantum opcodes
	// (memory parameter is nil and ignored)
	h := NewHandler()

	stack := newMockStack()
	gas := newMockGas(1_000_000)

	// QRISK_SYSTEMIC takes no stack inputs, pushes systemic risk
	err := h.ExecuteWithMemory(QRISK_SYSTEMIC, stack, gas, [20]byte{}, [32]byte{}, nil)
	if err != nil {
		t.Fatalf("ExecuteWithMemory QRISK_SYSTEMIC failed: %v", err)
	}

	if len(stack.data) != 1 {
		t.Fatalf("stack size = %d, want 1", len(stack.data))
	}
}

func TestHandler_Execute_BackwardCompatible(t *testing.T) {
	// Verify that Execute (without memory) still works for AGI opcodes
	h := NewHandler()
	h.AGI.SetPhi(1000)

	stack := newMockStack()
	gas := newMockGas(1_000_000)

	// QPHI does not need memory, so Execute (which passes nil memory) works
	err := h.Execute(QPHI, stack, gas, [20]byte{}, [32]byte{})
	if err != nil {
		t.Fatalf("Execute QPHI (backward compat) failed: %v", err)
	}
	if got := stack.top().Uint64(); got != 1000 {
		t.Errorf("QPHI backward compat = %d, want 1000", got)
	}
}
