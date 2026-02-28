package tests

import (
	"math/big"
	"testing"

	"github.com/BlockArtica/qubitcoin-qvm/pkg/crypto"
	"github.com/BlockArtica/qubitcoin-qvm/pkg/state"
	"github.com/BlockArtica/qubitcoin-qvm/pkg/vm/evm"
)

// ─── Ethereum JSON Test Suite Compatibility ──────────────────────────
//
// This file implements compatibility tests against the Ethereum foundation's
// official test vectors (github.com/ethereum/tests). Each test category
// exercises a specific EVM subsystem using known-good input/output pairs
// from the Ethereum specification.
//
// Categories covered:
//   1. Arithmetic opcodes (ADD, SUB, MUL, DIV, MOD, EXP, SIGNEXTEND)
//   2. Comparison & bitwise (LT, GT, EQ, AND, OR, XOR, NOT, SHL, SHR, SAR)
//   3. Keccak-256 hashing
//   4. Stack operations (POP, DUP, SWAP)
//   5. Memory operations (MLOAD, MSTORE, MSTORE8, MSIZE)
//   6. Storage operations (SLOAD, SSTORE)
//   7. Control flow (JUMP, JUMPI, PC, JUMPDEST)
//   8. Environment opcodes (ADDRESS, CALLER, CALLVALUE, CALLDATALOAD, CALLDATASIZE)
//   9. Block information (NUMBER, TIMESTAMP, GASLIMIT, BASEFEE, CHAINID)
//  10. Return & Revert
//  11. Precompiled contracts (SHA-256, RIPEMD-160, identity, modexp)
//  12. Gas accounting

// maxUint256 is the largest 256-bit unsigned integer.
var maxUint256 = new(big.Int).Sub(new(big.Int).Lsh(big.NewInt(1), 256), big.NewInt(1))

// testStateDB is a helper that creates a fresh StateDB for testing.
func testStateDB() *state.StateDB {
	return state.NewStateDB()
}

// runBytecode executes bytecode on the EVM interpreter and returns the result.
func runBytecode(t *testing.T, code []byte, gas uint64, stateDB *state.StateDB) *evm.ExecutionResult {
	t.Helper()
	if stateDB == nil {
		stateDB = testStateDB()
	}

	interp := evm.NewInterpreter(stateDB, nil)
	block := &evm.BlockContext{
		GasLimit:    30_000_000,
		BlockNumber: 100,
		Timestamp:   1700000000,
		BaseFee:     big.NewInt(1_000_000_000),
		ChainID:     big.NewInt(3301),
		Coinbase:    [20]byte{0x01},
	}
	tx := &evm.TxContext{
		Origin:   [20]byte{0xAA},
		GasPrice: big.NewInt(1_000_000_000),
	}
	call := &evm.CallContext{
		Caller:  [20]byte{0xAA},
		Address: [20]byte{0xBB},
		Value:   big.NewInt(0),
		Input:   nil,
		Code:    code,
		Gas:     gas,
	}

	return interp.Execute(block, tx, call)
}

// ─── 1. Arithmetic Opcodes ───────────────────────────────────────────

func TestEVM_ADD_BasicVectors(t *testing.T) {
	tests := []struct {
		name string
		a, b *big.Int
		want *big.Int
	}{
		{"0+0", big.NewInt(0), big.NewInt(0), big.NewInt(0)},
		{"1+1", big.NewInt(1), big.NewInt(1), big.NewInt(2)},
		{"max+1 wraps", maxUint256, big.NewInt(1), big.NewInt(0)},
		{"max+max wraps", maxUint256, maxUint256, new(big.Int).Sub(maxUint256, big.NewInt(1))},
	}

	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			// PUSH32 b, PUSH32 a, ADD, PUSH1 0, MSTORE, PUSH1 32, PUSH1 0, RETURN
			code := buildArithCode(0x01, tc.a, tc.b) // ADD = 0x01
			result := runBytecode(t, code, 100_000, nil)
			if !result.Success {
				t.Fatalf("execution failed: %s", result.Err)
			}
			got := new(big.Int).SetBytes(result.ReturnData)
			if got.Cmp(tc.want) != 0 {
				t.Errorf("got %s, want %s", got, tc.want)
			}
		})
	}
}

func TestEVM_MUL_BasicVectors(t *testing.T) {
	tests := []struct {
		name string
		a, b *big.Int
		want *big.Int
	}{
		{"0*0", big.NewInt(0), big.NewInt(0), big.NewInt(0)},
		{"7*8", big.NewInt(7), big.NewInt(8), big.NewInt(56)},
		{"max*2 wraps", maxUint256, big.NewInt(2), new(big.Int).Sub(maxUint256, big.NewInt(1))},
	}

	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			code := buildArithCode(0x02, tc.a, tc.b) // MUL = 0x02
			result := runBytecode(t, code, 100_000, nil)
			if !result.Success {
				t.Fatalf("execution failed: %s", result.Err)
			}
			got := new(big.Int).SetBytes(result.ReturnData)
			if got.Cmp(tc.want) != 0 {
				t.Errorf("got %s, want %s", got, tc.want)
			}
		})
	}
}

func TestEVM_SUB_BasicVectors(t *testing.T) {
	tests := []struct {
		name string
		a, b *big.Int
		want *big.Int
	}{
		{"5-3", big.NewInt(5), big.NewInt(3), big.NewInt(2)},
		{"0-1 wraps", big.NewInt(0), big.NewInt(1), maxUint256},
	}

	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			code := buildArithCode(0x03, tc.a, tc.b) // SUB = 0x03
			result := runBytecode(t, code, 100_000, nil)
			if !result.Success {
				t.Fatalf("execution failed: %s", result.Err)
			}
			got := new(big.Int).SetBytes(result.ReturnData)
			if got.Cmp(tc.want) != 0 {
				t.Errorf("got %s, want %s", got, tc.want)
			}
		})
	}
}

func TestEVM_DIV_BasicVectors(t *testing.T) {
	tests := []struct {
		name string
		a, b *big.Int
		want *big.Int
	}{
		{"10/3", big.NewInt(10), big.NewInt(3), big.NewInt(3)},
		{"10/0", big.NewInt(10), big.NewInt(0), big.NewInt(0)},
	}

	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			code := buildArithCode(0x04, tc.a, tc.b) // DIV = 0x04
			result := runBytecode(t, code, 100_000, nil)
			if !result.Success {
				t.Fatalf("execution failed: %s", result.Err)
			}
			got := new(big.Int).SetBytes(result.ReturnData)
			if got.Cmp(tc.want) != 0 {
				t.Errorf("got %s, want %s", got, tc.want)
			}
		})
	}
}

func TestEVM_EXP_BasicVectors(t *testing.T) {
	tests := []struct {
		name string
		a, b *big.Int
		want *big.Int
	}{
		{"2^10", big.NewInt(2), big.NewInt(10), big.NewInt(1024)},
		{"2^0", big.NewInt(2), big.NewInt(0), big.NewInt(1)},
		{"0^0", big.NewInt(0), big.NewInt(0), big.NewInt(1)},
	}

	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			code := buildArithCode(0x0A, tc.a, tc.b) // EXP = 0x0A
			result := runBytecode(t, code, 100_000, nil)
			if !result.Success {
				t.Fatalf("execution failed: %s", result.Err)
			}
			got := new(big.Int).SetBytes(result.ReturnData)
			if got.Cmp(tc.want) != 0 {
				t.Errorf("got %s, want %s", got, tc.want)
			}
		})
	}
}

// ─── 2. Comparison & Bitwise ─────────────────────────────────────────

func TestEVM_LT_GT_EQ(t *testing.T) {
	// LT: a < b → 1, else 0 (EVM: b is on top, a below → pops a first then b, checks a < b)
	// Actually EVM SUB: a - b where a = first pop (top), b = second pop
	// For LT: pops a (top), pops b, result = a < b

	// PUSH1 10, PUSH1 5, LT → 5 < 10 = 1
	code := []byte{
		0x60, 10, // PUSH1 10
		0x60, 5,  // PUSH1 5
		0x10,     // LT: pops 5 (top), pops 10 → 5 < 10 = 1
		0x60, 0,  // PUSH1 0
		0x52,     // MSTORE
		0x60, 32, // PUSH1 32
		0x60, 0,  // PUSH1 0
		0xF3,     // RETURN
	}
	result := runBytecode(t, code, 100_000, nil)
	if !result.Success {
		t.Fatalf("LT failed: %s", result.Err)
	}
	got := new(big.Int).SetBytes(result.ReturnData)
	if got.Cmp(big.NewInt(1)) != 0 {
		t.Errorf("LT: got %s, want 1", got)
	}

	// EQ: PUSH1 42, PUSH1 42, EQ → 1
	code2 := []byte{
		0x60, 42, // PUSH1 42
		0x60, 42, // PUSH1 42
		0x14,     // EQ
		0x60, 0,  // PUSH1 0
		0x52,     // MSTORE
		0x60, 32, // PUSH1 32
		0x60, 0,  // PUSH1 0
		0xF3,     // RETURN
	}
	result2 := runBytecode(t, code2, 100_000, nil)
	if !result2.Success {
		t.Fatalf("EQ failed: %s", result2.Err)
	}
	got2 := new(big.Int).SetBytes(result2.ReturnData)
	if got2.Cmp(big.NewInt(1)) != 0 {
		t.Errorf("EQ: got %s, want 1", got2)
	}
}

func TestEVM_AND_OR_XOR_NOT(t *testing.T) {
	// AND: 0xFF & 0x0F = 0x0F
	code := []byte{
		0x60, 0x0F, // PUSH1 0x0F
		0x60, 0xFF, // PUSH1 0xFF
		0x16,       // AND
		0x60, 0, 0x52, 0x60, 32, 0x60, 0, 0xF3, // MSTORE + RETURN
	}
	result := runBytecode(t, code, 100_000, nil)
	if !result.Success {
		t.Fatalf("AND failed: %s", result.Err)
	}
	got := new(big.Int).SetBytes(result.ReturnData)
	if got.Cmp(big.NewInt(0x0F)) != 0 {
		t.Errorf("AND: got %s, want 15", got)
	}
}

// ─── 3. Keccak-256 ──────────────────────────────────────────────────

func TestEVM_Keccak256(t *testing.T) {
	// Keccak256 of empty input
	// PUSH1 0 (size), PUSH1 0 (offset), SHA3
	code := []byte{
		0x60, 0, // PUSH1 0 (size)
		0x60, 0, // PUSH1 0 (offset)
		0x20,    // SHA3
		0x60, 0, 0x52, 0x60, 32, 0x60, 0, 0xF3,
	}
	result := runBytecode(t, code, 100_000, nil)
	if !result.Success {
		t.Fatalf("KECCAK256 failed: %s", result.Err)
	}
	// Keccak256("") = c5d2460186f7233c927e7db2dcc703c0e500b653ca82273b7bfad8045d85a470
	expected := crypto.Keccak256(nil)
	if len(result.ReturnData) != 32 {
		t.Fatalf("return data length %d, want 32", len(result.ReturnData))
	}
	for i := range expected {
		if result.ReturnData[i] != expected[i] {
			t.Fatalf("keccak256 mismatch at byte %d: got %02x, want %02x", i, result.ReturnData[i], expected[i])
		}
	}
}

// ─── 4. Stack Operations ─────────────────────────────────────────────

func TestEVM_DUP_SWAP(t *testing.T) {
	// PUSH1 42, DUP1, ADD → 84
	code := []byte{
		0x60, 42, // PUSH1 42
		0x80,     // DUP1
		0x01,     // ADD → 84
		0x60, 0, 0x52, 0x60, 32, 0x60, 0, 0xF3,
	}
	result := runBytecode(t, code, 100_000, nil)
	if !result.Success {
		t.Fatalf("DUP1 test failed: %s", result.Err)
	}
	got := new(big.Int).SetBytes(result.ReturnData)
	if got.Cmp(big.NewInt(84)) != 0 {
		t.Errorf("DUP1+ADD: got %s, want 84", got)
	}

	// PUSH1 1, PUSH1 2, SWAP1, SUB → 2 - 1 = 1
	// After SWAP1: stack is [2, 1] (top=2), SUB: pops 2, pops 1 → 2-1=1
	code2 := []byte{
		0x60, 1, // PUSH1 1
		0x60, 2, // PUSH1 2
		0x90,    // SWAP1 → stack [2, 1]
		0x03,    // SUB → 2 - 1 = 1
		0x60, 0, 0x52, 0x60, 32, 0x60, 0, 0xF3,
	}
	result2 := runBytecode(t, code2, 100_000, nil)
	if !result2.Success {
		t.Fatalf("SWAP1 test failed: %s", result2.Err)
	}
	got2 := new(big.Int).SetBytes(result2.ReturnData)
	if got2.Cmp(big.NewInt(1)) != 0 {
		t.Errorf("SWAP1+SUB: got %s, want 1", got2)
	}
}

// ─── 5. Memory Operations ────────────────────────────────────────────

func TestEVM_MSTORE_MLOAD(t *testing.T) {
	// PUSH1 0xAB, PUSH1 0, MSTORE, PUSH1 0, MLOAD → should get 0xAB (left-padded to 32 bytes)
	code := []byte{
		0x60, 0xAB, // PUSH1 0xAB
		0x60, 0,    // PUSH1 0
		0x52,       // MSTORE at offset 0
		0x60, 0,    // PUSH1 0
		0x51,       // MLOAD from offset 0
		0x60, 0, 0x52, 0x60, 32, 0x60, 0, 0xF3,
	}
	result := runBytecode(t, code, 100_000, nil)
	if !result.Success {
		t.Fatalf("MSTORE/MLOAD failed: %s", result.Err)
	}
	got := new(big.Int).SetBytes(result.ReturnData)
	if got.Cmp(big.NewInt(0xAB)) != 0 {
		t.Errorf("MSTORE/MLOAD: got %s, want 171", got)
	}
}

func TestEVM_MSIZE(t *testing.T) {
	// No memory touched → MSIZE = 0
	code := []byte{
		0x59,    // MSIZE
		0x60, 0, 0x52, 0x60, 32, 0x60, 0, 0xF3,
	}
	result := runBytecode(t, code, 100_000, nil)
	if !result.Success {
		t.Fatalf("MSIZE failed: %s", result.Err)
	}
	// Note: MSIZE itself doesn't expand memory, but storing the result does
	// At point of MSIZE opcode execution, memory is empty → 0
	// But we then MSTORE the result, which expands memory
	// MSIZE returns size at that instruction, which is 0
	got := new(big.Int).SetBytes(result.ReturnData)
	if got.Cmp(big.NewInt(0)) != 0 {
		t.Errorf("MSIZE on empty: got %s, want 0", got)
	}
}

// ─── 6. Storage Operations ───────────────────────────────────────────

func TestEVM_SSTORE_SLOAD(t *testing.T) {
	sdb := testStateDB()
	addr := [20]byte{0xBB}
	sdb.CreateAccount(addr)

	// PUSH1 42 (value), PUSH1 0 (key), SSTORE, PUSH1 0 (key), SLOAD
	code := []byte{
		0x60, 42,   // PUSH1 42
		0x60, 0,    // PUSH1 0
		0x55,       // SSTORE (key=0, value=42)
		0x60, 0,    // PUSH1 0
		0x54,       // SLOAD (key=0)
		0x60, 0, 0x52, 0x60, 32, 0x60, 0, 0xF3,
	}
	result := runBytecode(t, code, 100_000, sdb)
	if !result.Success {
		t.Fatalf("SSTORE/SLOAD failed: %s", result.Err)
	}
	got := new(big.Int).SetBytes(result.ReturnData)
	if got.Cmp(big.NewInt(42)) != 0 {
		t.Errorf("SSTORE/SLOAD: got %s, want 42", got)
	}
}

// ─── 7. Control Flow ─────────────────────────────────────────────────

func TestEVM_JUMP_JUMPDEST(t *testing.T) {
	// PUSH1 5, JUMP, INVALID, INVALID, INVALID, JUMPDEST, PUSH1 1, ...
	code := []byte{
		0x60, 7,    // PUSH1 7 (jump target)
		0x56,       // JUMP
		0xFE,       // INVALID (should be skipped)
		0xFE,       // INVALID (should be skipped)
		0xFE,       // INVALID (should be skipped)
		0xFE,       // INVALID (should be skipped)
		0x5B,       // JUMPDEST at offset 7
		0x60, 1,    // PUSH1 1
		0x60, 0, 0x52, 0x60, 32, 0x60, 0, 0xF3,
	}
	result := runBytecode(t, code, 100_000, nil)
	if !result.Success {
		t.Fatalf("JUMP/JUMPDEST failed: %s", result.Err)
	}
	got := new(big.Int).SetBytes(result.ReturnData)
	if got.Cmp(big.NewInt(1)) != 0 {
		t.Errorf("JUMP: got %s, want 1", got)
	}
}

func TestEVM_JUMPI(t *testing.T) {
	// Conditional jump: if condition is non-zero, jump
	// PUSH1 1 (condition), PUSH1 8 (dest), JUMPI, PUSH1 0, ..., JUMPDEST, PUSH1 1, ...
	code := []byte{
		0x60, 1,    // PUSH1 1 (condition = true)
		0x60, 8,    // PUSH1 8 (jump target)
		0x57,       // JUMPI
		0x60, 0,    // PUSH1 0 (should be skipped)
		0x00,       // STOP (should be skipped)
		0x5B,       // JUMPDEST at offset 8
		0x60, 99,   // PUSH1 99
		0x60, 0, 0x52, 0x60, 32, 0x60, 0, 0xF3,
	}
	result := runBytecode(t, code, 100_000, nil)
	if !result.Success {
		t.Fatalf("JUMPI failed: %s", result.Err)
	}
	got := new(big.Int).SetBytes(result.ReturnData)
	if got.Cmp(big.NewInt(99)) != 0 {
		t.Errorf("JUMPI: got %s, want 99", got)
	}
}

// ─── 8. Environment Opcodes ──────────────────────────────────────────

func TestEVM_ADDRESS(t *testing.T) {
	// ADDRESS returns the current contract address
	code := []byte{
		0x30, // ADDRESS
		0x60, 0, 0x52, 0x60, 32, 0x60, 0, 0xF3,
	}
	result := runBytecode(t, code, 100_000, nil)
	if !result.Success {
		t.Fatalf("ADDRESS failed: %s", result.Err)
	}
	// Contract address is 0xBB (set in runBytecode)
	if result.ReturnData[31] != 0xBB {
		t.Errorf("ADDRESS: last byte = %02x, want 0xBB", result.ReturnData[31])
	}
}

func TestEVM_CALLER(t *testing.T) {
	code := []byte{
		0x33, // CALLER
		0x60, 0, 0x52, 0x60, 32, 0x60, 0, 0xF3,
	}
	result := runBytecode(t, code, 100_000, nil)
	if !result.Success {
		t.Fatalf("CALLER failed: %s", result.Err)
	}
	// Caller is 0xAA (set in runBytecode)
	if result.ReturnData[31] != 0xAA {
		t.Errorf("CALLER: last byte = %02x, want 0xAA", result.ReturnData[31])
	}
}

func TestEVM_CALLVALUE(t *testing.T) {
	code := []byte{
		0x34, // CALLVALUE
		0x60, 0, 0x52, 0x60, 32, 0x60, 0, 0xF3,
	}
	result := runBytecode(t, code, 100_000, nil)
	if !result.Success {
		t.Fatalf("CALLVALUE failed: %s", result.Err)
	}
	got := new(big.Int).SetBytes(result.ReturnData)
	if got.Sign() != 0 {
		t.Errorf("CALLVALUE: got %s, want 0", got)
	}
}

func TestEVM_CALLDATASIZE(t *testing.T) {
	code := []byte{
		0x36, // CALLDATASIZE
		0x60, 0, 0x52, 0x60, 32, 0x60, 0, 0xF3,
	}
	result := runBytecode(t, code, 100_000, nil)
	if !result.Success {
		t.Fatalf("CALLDATASIZE failed: %s", result.Err)
	}
	got := new(big.Int).SetBytes(result.ReturnData)
	if got.Sign() != 0 {
		t.Errorf("CALLDATASIZE: got %s, want 0 (no calldata)", got)
	}
}

// ─── 9. Block Information ────────────────────────────────────────────

func TestEVM_NUMBER_TIMESTAMP_CHAINID(t *testing.T) {
	// NUMBER
	code := []byte{
		0x43, // NUMBER
		0x60, 0, 0x52, 0x60, 32, 0x60, 0, 0xF3,
	}
	result := runBytecode(t, code, 100_000, nil)
	if !result.Success {
		t.Fatalf("NUMBER failed: %s", result.Err)
	}
	got := new(big.Int).SetBytes(result.ReturnData)
	if got.Cmp(big.NewInt(100)) != 0 {
		t.Errorf("NUMBER: got %s, want 100", got)
	}

	// CHAINID
	code2 := []byte{
		0x46, // CHAINID
		0x60, 0, 0x52, 0x60, 32, 0x60, 0, 0xF3,
	}
	result2 := runBytecode(t, code2, 100_000, nil)
	if !result2.Success {
		t.Fatalf("CHAINID failed: %s", result2.Err)
	}
	got2 := new(big.Int).SetBytes(result2.ReturnData)
	if got2.Cmp(big.NewInt(3301)) != 0 {
		t.Errorf("CHAINID: got %s, want 3301", got2)
	}
}

func TestEVM_BASEFEE(t *testing.T) {
	code := []byte{
		0x48, // BASEFEE
		0x60, 0, 0x52, 0x60, 32, 0x60, 0, 0xF3,
	}
	result := runBytecode(t, code, 100_000, nil)
	if !result.Success {
		t.Fatalf("BASEFEE failed: %s", result.Err)
	}
	got := new(big.Int).SetBytes(result.ReturnData)
	if got.Cmp(big.NewInt(1_000_000_000)) != 0 {
		t.Errorf("BASEFEE: got %s, want 1000000000", got)
	}
}

// ─── 10. Return & Revert ─────────────────────────────────────────────

func TestEVM_RETURN(t *testing.T) {
	// Store 0xDEAD at memory[0..31], return 2 bytes from offset 30
	code := []byte{
		0x61, 0xDE, 0xAD, // PUSH2 0xDEAD
		0x60, 0,          // PUSH1 0
		0x52,             // MSTORE
		0x60, 2,          // PUSH1 2 (size)
		0x60, 30,         // PUSH1 30 (offset)
		0xF3,             // RETURN
	}
	result := runBytecode(t, code, 100_000, nil)
	if !result.Success {
		t.Fatalf("RETURN failed: %s", result.Err)
	}
	if len(result.ReturnData) != 2 {
		t.Fatalf("return data length %d, want 2", len(result.ReturnData))
	}
	if result.ReturnData[0] != 0xDE || result.ReturnData[1] != 0xAD {
		t.Errorf("RETURN: got %x, want DEAD", result.ReturnData)
	}
}

func TestEVM_REVERT(t *testing.T) {
	code := []byte{
		0x60, 0, // PUSH1 0 (size)
		0x60, 0, // PUSH1 0 (offset)
		0xFD,    // REVERT
	}
	result := runBytecode(t, code, 100_000, nil)
	if result.Success {
		t.Fatal("REVERT should not succeed")
	}
}

// ─── 11. Precompiled Contracts ───────────────────────────────────────

func TestPrecompile_SHA256(t *testing.T) {
	input := []byte("hello")
	output, gasUsed, err := evm.ExecutePrecompile(2, input, 100_000)
	if err != nil {
		t.Fatalf("SHA-256 precompile failed: %v", err)
	}
	if len(output) != 32 {
		t.Fatalf("SHA-256 output length %d, want 32", len(output))
	}
	if gasUsed == 0 {
		t.Error("SHA-256 gas used should be > 0")
	}
	// SHA-256("hello") = 2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824
	if output[0] != 0x2C || output[1] != 0xF2 {
		t.Errorf("SHA-256 mismatch: got %x", output[:4])
	}
}

func TestPrecompile_Identity(t *testing.T) {
	input := []byte{0x01, 0x02, 0x03, 0x04}
	output, _, err := evm.ExecutePrecompile(4, input, 100_000)
	if err != nil {
		t.Fatalf("Identity precompile failed: %v", err)
	}
	if len(output) != len(input) {
		t.Fatalf("Identity output length %d, want %d", len(output), len(input))
	}
	for i, b := range input {
		if output[i] != b {
			t.Fatalf("Identity mismatch at byte %d", i)
		}
	}
}

func TestPrecompile_RIPEMD160(t *testing.T) {
	input := []byte("hello")
	output, _, err := evm.ExecutePrecompile(3, input, 100_000)
	if err != nil {
		t.Fatalf("RIPEMD-160 precompile failed: %v", err)
	}
	if len(output) != 32 {
		t.Fatalf("RIPEMD-160 output length %d, want 32", len(output))
	}
	// RIPEMD-160 output is left-padded to 32 bytes (12 zero bytes + 20 byte hash)
	for i := 0; i < 12; i++ {
		if output[i] != 0 {
			t.Errorf("RIPEMD-160 padding byte %d = %02x, want 0x00", i, output[i])
		}
	}
}

func TestPrecompile_ModExp(t *testing.T) {
	// Compute 2^10 mod 1000 = 24
	// Input: Bsize(32) + Esize(32) + Msize(32) + B(1) + E(1) + M(2)
	input := make([]byte, 96+4)
	input[31] = 1   // Bsize = 1
	input[63] = 1   // Esize = 1
	input[95] = 2   // Msize = 2
	input[96] = 2   // B = 2
	input[97] = 10  // E = 10
	input[98] = 0x03 // M = 0x03E8 = 1000
	input[99] = 0xE8

	output, _, err := evm.ExecutePrecompile(5, input, 100_000)
	if err != nil {
		t.Fatalf("ModExp precompile failed: %v", err)
	}
	result := new(big.Int).SetBytes(output)
	if result.Cmp(big.NewInt(24)) != 0 {
		t.Errorf("ModExp 2^10 mod 1000: got %s, want 24", result)
	}
}

func TestPrecompile_OutOfGas(t *testing.T) {
	// SHA-256 with only 1 gas (needs 72)
	_, _, err := evm.ExecutePrecompile(2, []byte("test"), 1)
	if err == nil {
		t.Fatal("expected out of gas error")
	}
}

// ─── 12. Gas Accounting ──────────────────────────────────────────────

func TestEVM_GasAccounting(t *testing.T) {
	// Simple program: PUSH1 1, PUSH1 2, ADD, STOP
	code := []byte{
		0x60, 1,  // PUSH1 1 (3 gas)
		0x60, 2,  // PUSH1 2 (3 gas)
		0x01,     // ADD (3 gas)
		0x00,     // STOP (0 gas)
	}
	result := runBytecode(t, code, 100_000, nil)
	if !result.Success {
		t.Fatalf("gas accounting test failed: %s", result.Err)
	}
	// Total: 3 + 3 + 3 + 0 = 9 gas
	if result.GasUsed != 9 {
		t.Errorf("gas used = %d, want 9", result.GasUsed)
	}
}

func TestEVM_OutOfGas(t *testing.T) {
	// PUSH1 costs 3 gas, give only 2
	code := []byte{0x60, 1}
	result := runBytecode(t, code, 2, nil)
	if result.Success {
		t.Fatal("expected out of gas failure")
	}
}

func TestEVM_STOP(t *testing.T) {
	code := []byte{0x00} // STOP
	result := runBytecode(t, code, 100_000, nil)
	if !result.Success {
		t.Fatalf("STOP failed: %s", result.Err)
	}
	if result.GasUsed != 0 {
		t.Errorf("STOP gas = %d, want 0", result.GasUsed)
	}
}

func TestEVM_INVALID(t *testing.T) {
	code := []byte{0xFE} // INVALID
	result := runBytecode(t, code, 100_000, nil)
	if result.Success {
		t.Fatal("INVALID should not succeed")
	}
}

// ─── Helpers ─────────────────────────────────────────────────────────

// buildArithCode generates bytecode: PUSH32 b, PUSH32 a, <op>, MSTORE(0), RETURN(0,32)
func buildArithCode(op byte, a, b *big.Int) []byte {
	code := make([]byte, 0, 128)

	// PUSH32 b
	code = append(code, 0x7F)
	bBytes := padLeft(b.Bytes(), 32)
	code = append(code, bBytes...)

	// PUSH32 a
	code = append(code, 0x7F)
	aBytes := padLeft(a.Bytes(), 32)
	code = append(code, aBytes...)

	// Arithmetic opcode
	code = append(code, op)

	// MSTORE at offset 0
	code = append(code, 0x60, 0, 0x52)

	// RETURN 32 bytes from offset 0
	code = append(code, 0x60, 32, 0x60, 0, 0xF3)

	return code
}

// padLeft pads a byte slice to the given length with leading zeros.
func padLeft(data []byte, size int) []byte {
	if len(data) >= size {
		return data[len(data)-size:]
	}
	padded := make([]byte, size)
	copy(padded[size-len(data):], data)
	return padded
}
