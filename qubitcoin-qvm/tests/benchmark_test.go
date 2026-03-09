package tests

import (
	"crypto/rand"
	"math/big"
	"testing"

	"github.com/BlockArtica/qubitcoin-qvm/pkg/compliance"
	"github.com/BlockArtica/qubitcoin-qvm/pkg/crypto"
	"github.com/BlockArtica/qubitcoin-qvm/pkg/state"
	"github.com/BlockArtica/qubitcoin-qvm/pkg/vm/evm"
	"github.com/BlockArtica/qubitcoin-qvm/pkg/vm/quantum"
)

// ─── EVM Benchmarks ──────────────────────────────────────────────────

// BenchmarkEVM_SimpleTransfer benchmarks a minimal value transfer (21000 gas equivalent).
func BenchmarkEVM_SimpleTransfer(b *testing.B) {
	// PUSH1 0, PUSH1 0, RETURN (simplest possible execution)
	code := []byte{0x60, 0, 0x60, 0, 0xF3}
	sdb := state.NewStateDB()
	interp := evm.NewInterpreter(sdb, nil)
	block, tx, call := makeTestContextArgs(code, 100_000)

	b.ResetTimer()
	b.ReportAllocs()
	for i := 0; i < b.N; i++ {
		call.Gas = 100_000
		interp.Execute(block, tx, call)
	}
}

// BenchmarkEVM_ArithmeticLoop benchmarks a tight arithmetic loop.
func BenchmarkEVM_ArithmeticLoop(b *testing.B) {
	// 100 iterations of ADD: PUSH1 0, then 100x (PUSH1 1, ADD)
	code := make([]byte, 0, 300)
	code = append(code, 0x60, 0) // PUSH1 0
	for i := 0; i < 100; i++ {
		code = append(code, 0x60, 1) // PUSH1 1
		code = append(code, 0x01)    // ADD
	}
	code = append(code, 0x60, 0, 0x52, 0x60, 32, 0x60, 0, 0xF3) // MSTORE + RETURN

	sdb := state.NewStateDB()
	interp := evm.NewInterpreter(sdb, nil)
	block, tx, call := makeTestContextArgs(code, 1_000_000)

	b.ResetTimer()
	b.ReportAllocs()
	for i := 0; i < b.N; i++ {
		call.Gas = 1_000_000
		interp.Execute(block, tx, call)
	}
}

// BenchmarkEVM_Keccak256 benchmarks the Keccak-256 opcode.
func BenchmarkEVM_Keccak256(b *testing.B) {
	// Write 32 bytes to memory, then hash them
	code := []byte{
		0x7F, // PUSH32 (32 bytes of data)
	}
	data := make([]byte, 32)
	rand.Read(data)
	code = append(code, data...)
	code = append(code,
		0x60, 0,  // PUSH1 0
		0x52,     // MSTORE
		0x60, 32, // PUSH1 32 (size)
		0x60, 0,  // PUSH1 0 (offset)
		0x20,     // SHA3
		0x60, 0, 0x52, 0x60, 32, 0x60, 0, 0xF3,
	)

	sdb := state.NewStateDB()
	interp := evm.NewInterpreter(sdb, nil)
	block, tx, call := makeTestContextArgs(code, 1_000_000)

	b.ResetTimer()
	b.ReportAllocs()
	for i := 0; i < b.N; i++ {
		call.Gas = 1_000_000
		interp.Execute(block, tx, call)
	}
}

// BenchmarkEVM_MemoryExpansion benchmarks memory allocation/expansion.
func BenchmarkEVM_MemoryExpansion(b *testing.B) {
	// MSTORE at increasingly large offsets (1KB expansion)
	code := make([]byte, 0, 200)
	for offset := 0; offset < 1024; offset += 32 {
		code = append(code, 0x60, 0xFF)            // PUSH1 value
		code = append(code, 0x61)                   // PUSH2 offset
		code = append(code, byte(offset>>8), byte(offset))
		code = append(code, 0x52)                   // MSTORE
	}
	code = append(code, 0x00) // STOP

	sdb := state.NewStateDB()
	interp := evm.NewInterpreter(sdb, nil)
	block, tx, call := makeTestContextArgs(code, 10_000_000)

	b.ResetTimer()
	b.ReportAllocs()
	for i := 0; i < b.N; i++ {
		call.Gas = 10_000_000
		interp.Execute(block, tx, call)
	}
}

// BenchmarkEVM_StorageWrite benchmarks SSTORE operations.
func BenchmarkEVM_StorageWrite(b *testing.B) {
	// Write 10 storage slots
	code := make([]byte, 0, 100)
	for slot := byte(0); slot < 10; slot++ {
		code = append(code, 0x60, slot+1) // PUSH1 value
		code = append(code, 0x60, slot)   // PUSH1 key
		code = append(code, 0x55)         // SSTORE
	}
	code = append(code, 0x00) // STOP

	sdb := state.NewStateDB()
	addr := [20]byte{0xBB}
	sdb.CreateAccount(addr)
	interp := evm.NewInterpreter(sdb, nil)
	block, tx, call := makeTestContextArgs(code, 10_000_000)

	b.ResetTimer()
	b.ReportAllocs()
	for i := 0; i < b.N; i++ {
		call.Gas = 10_000_000
		interp.Execute(block, tx, call)
	}
}

// BenchmarkEVM_PUSH_POP benchmarks raw stack throughput.
func BenchmarkEVM_PUSH_POP(b *testing.B) {
	// 100 PUSH1/POP cycles
	code := make([]byte, 0, 300)
	for i := 0; i < 100; i++ {
		code = append(code, 0x60, byte(i)) // PUSH1
		code = append(code, 0x50)          // POP
	}
	code = append(code, 0x00) // STOP

	sdb := state.NewStateDB()
	interp := evm.NewInterpreter(sdb, nil)
	block, tx, call := makeTestContextArgs(code, 1_000_000)

	b.ResetTimer()
	b.ReportAllocs()
	for i := 0; i < b.N; i++ {
		call.Gas = 1_000_000
		interp.Execute(block, tx, call)
	}
}

// ─── Precompile Benchmarks ───────────────────────────────────────────

func BenchmarkPrecompile_SHA256(b *testing.B) {
	input := make([]byte, 64)
	rand.Read(input)

	b.ResetTimer()
	b.ReportAllocs()
	for i := 0; i < b.N; i++ {
		evm.ExecutePrecompile(2, input, 100_000)
	}
}

func BenchmarkPrecompile_RIPEMD160(b *testing.B) {
	input := make([]byte, 64)
	rand.Read(input)

	b.ResetTimer()
	b.ReportAllocs()
	for i := 0; i < b.N; i++ {
		evm.ExecutePrecompile(3, input, 100_000)
	}
}

func BenchmarkPrecompile_Identity(b *testing.B) {
	input := make([]byte, 128)
	rand.Read(input)

	b.ResetTimer()
	b.ReportAllocs()
	for i := 0; i < b.N; i++ {
		evm.ExecutePrecompile(4, input, 100_000)
	}
}

func BenchmarkPrecompile_ModExp_Small(b *testing.B) {
	// 2^10 mod 1000
	input := make([]byte, 100)
	input[31] = 1  // Bsize = 1
	input[63] = 1  // Esize = 1
	input[95] = 2  // Msize = 2
	input[96] = 2  // B = 2
	input[97] = 10 // E = 10
	input[98] = 0x03
	input[99] = 0xE8 // M = 1000

	b.ResetTimer()
	b.ReportAllocs()
	for i := 0; i < b.N; i++ {
		evm.ExecutePrecompile(5, input, 100_000)
	}
}

// ─── Quantum Benchmarks ─────────────────────────────────────────────

func BenchmarkQuantum_CreateState_4Qubit(b *testing.B) {
	sm := quantum.NewStateManager()
	owner := [20]byte{0xAA}

	b.ResetTimer()
	b.ReportAllocs()
	for i := 0; i < b.N; i++ {
		sm.CreateState(4, owner)
	}
}

func BenchmarkQuantum_CreateState_8Qubit(b *testing.B) {
	sm := quantum.NewStateManager()
	owner := [20]byte{0xAA}

	b.ResetTimer()
	b.ReportAllocs()
	for i := 0; i < b.N; i++ {
		sm.CreateState(8, owner)
	}
}

func BenchmarkQuantum_ApplyGate_Hadamard(b *testing.B) {
	sm := quantum.NewStateManager()
	owner := [20]byte{0xAA}
	id, _ := sm.CreateState(4, owner)
	qs, _ := sm.GetState(id)

	b.ResetTimer()
	b.ReportAllocs()
	for i := 0; i < b.N; i++ {
		quantum.ApplyGate(qs, quantum.GateH, 0, 0)
	}
}

func BenchmarkQuantum_ApplyGate_CNOT(b *testing.B) {
	sm := quantum.NewStateManager()
	owner := [20]byte{0xAA}
	id, _ := sm.CreateState(4, owner)
	qs, _ := sm.GetState(id)

	b.ResetTimer()
	b.ReportAllocs()
	for i := 0; i < b.N; i++ {
		quantum.ApplyCNOT(qs, 0, 1)
	}
}

func BenchmarkQuantum_Measure_4Qubit(b *testing.B) {
	sm := quantum.NewStateManager()
	owner := [20]byte{0xAA}
	blockSeed := [32]byte{0x01, 0x02, 0x03}

	b.ResetTimer()
	b.ReportAllocs()
	for i := 0; i < b.N; i++ {
		id, _ := sm.CreateState(4, owner)
		sm.MeasureState(id, blockSeed)
	}
}

func BenchmarkQuantum_Entangle(b *testing.B) {
	sm := quantum.NewStateManager()
	owner := [20]byte{0xAA}

	b.ResetTimer()
	b.ReportAllocs()
	for i := 0; i < b.N; i++ {
		idA, _ := sm.CreateState(2, owner)
		idB, _ := sm.CreateState(2, owner)
		sm.Entangle(idA, idB)
	}
}

func BenchmarkQuantum_VerifyState(b *testing.B) {
	sm := quantum.NewStateManager()
	owner := [20]byte{0xAA}
	id, _ := sm.CreateState(4, owner)

	b.ResetTimer()
	b.ReportAllocs()
	for i := 0; i < b.N; i++ {
		sm.VerifyState(id)
	}
}

// ─── State DB Benchmarks ─────────────────────────────────────────────

func BenchmarkStateDB_GetSetBalance(b *testing.B) {
	sdb := state.NewStateDB()
	addr := [20]byte{0x01}
	sdb.CreateAccount(addr)

	b.ResetTimer()
	b.ReportAllocs()
	for i := 0; i < b.N; i++ {
		sdb.SetBalance(addr, big.NewInt(int64(i)))
		sdb.GetBalance(addr)
	}
}

func BenchmarkStateDB_GetSetStorage(b *testing.B) {
	sdb := state.NewStateDB()
	addr := [20]byte{0x01}
	sdb.CreateAccount(addr)
	key := [32]byte{0x01}
	val := [32]byte{0xFF}

	b.ResetTimer()
	b.ReportAllocs()
	for i := 0; i < b.N; i++ {
		sdb.SetStorage(addr, key, val)
		sdb.GetStorage(addr, key)
	}
}

func BenchmarkStateDB_SnapshotRevert(b *testing.B) {
	sdb := state.NewStateDB()
	addr := [20]byte{0x01}
	sdb.CreateAccount(addr)

	b.ResetTimer()
	b.ReportAllocs()
	for i := 0; i < b.N; i++ {
		snap := sdb.Snapshot()
		sdb.SetBalance(addr, big.NewInt(1000))
		sdb.RevertToSnapshot(snap)
	}
}

func BenchmarkStateDB_CreateAccount(b *testing.B) {
	sdb := state.NewStateDB()

	b.ResetTimer()
	b.ReportAllocs()
	for i := 0; i < b.N; i++ {
		addr := [20]byte{byte(i >> 8), byte(i)}
		sdb.CreateAccount(addr)
	}
}

func BenchmarkStateDB_ComputeStateRoot(b *testing.B) {
	sdb := state.NewStateDB()
	// Pre-populate 100 accounts
	for i := 0; i < 100; i++ {
		addr := [20]byte{byte(i)}
		sdb.CreateAccount(addr)
		sdb.SetBalance(addr, big.NewInt(int64(i*1000)))
	}

	b.ResetTimer()
	b.ReportAllocs()
	for i := 0; i < b.N; i++ {
		sdb.ComputeStateRoot()
	}
}

// ─── Crypto Benchmarks ───────────────────────────────────────────────

func BenchmarkCrypto_Keccak256_32B(b *testing.B) {
	data := make([]byte, 32)
	rand.Read(data)

	b.ResetTimer()
	b.ReportAllocs()
	for i := 0; i < b.N; i++ {
		crypto.Keccak256(data)
	}
}

func BenchmarkCrypto_Keccak256_1KB(b *testing.B) {
	data := make([]byte, 1024)
	rand.Read(data)

	b.ResetTimer()
	b.ReportAllocs()
	for i := 0; i < b.N; i++ {
		crypto.Keccak256(data)
	}
}

func BenchmarkCrypto_SHA256_32B(b *testing.B) {
	data := make([]byte, 32)
	rand.Read(data)

	b.ResetTimer()
	b.ReportAllocs()
	for i := 0; i < b.N; i++ {
		crypto.SHA256Hash(data)
	}
}

func BenchmarkCrypto_AddressFromPubkey(b *testing.B) {
	pubkey := make([]byte, 64)
	rand.Read(pubkey)

	b.ResetTimer()
	b.ReportAllocs()
	for i := 0; i < b.N; i++ {
		crypto.AddressFromPublicKey(pubkey)
	}
}

// ─── Compliance Benchmarks ───────────────────────────────────────────

func BenchmarkCompliance_KYC_CheckTransaction(b *testing.B) {
	reg := compliance.NewKYCRegistry()
	addr := [20]byte{0xAA, 0xBB}
	reg.Register(&compliance.KYCStatus{
		Address: addr,
		Tier:    compliance.TierProfessional,
	})

	b.ResetTimer()
	b.ReportAllocs()
	for i := 0; i < b.N; i++ {
		reg.CheckTransactionAllowed(addr, 500_000, 100)
	}
}

func BenchmarkCompliance_AML_RecordTransaction(b *testing.B) {
	mon := compliance.NewAMLMonitor()
	addr := [20]byte{0xAA, 0xBB}

	b.ResetTimer()
	b.ReportAllocs()
	for i := 0; i < b.N; i++ {
		mon.RecordTransaction(addr, 1000, uint64(i))
	}
}

func BenchmarkCompliance_Sanctions_Check(b *testing.B) {
	checker := compliance.NewSanctionsChecker()
	// Add 1000 sanctioned addresses
	for i := 0; i < 1000; i++ {
		addr := [20]byte{byte(i >> 8), byte(i)}
		checker.AddEntry(addr, "OFAC", 0)
	}

	b.ResetTimer()
	b.ReportAllocs()
	for i := 0; i < b.N; i++ {
		checker.IsSanctioned([20]byte{0xFF, 0xFF})
	}
}

func BenchmarkCompliance_Risk_ComputeRisk(b *testing.B) {
	scorer := compliance.NewRiskScorer()
	addr := [20]byte{0xAA, 0xBB}

	b.ResetTimer()
	b.ReportAllocs()
	for i := 0; i < b.N; i++ {
		scorer.ComputeRisk(addr, 50, 100_000, 1000, compliance.TierProfessional, 100)
	}
}

func BenchmarkCompliance_Risk_SystemicRisk(b *testing.B) {
	scorer := compliance.NewRiskScorer()

	b.ResetTimer()
	b.ReportAllocs()
	for i := 0; i < b.N; i++ {
		scorer.ComputeSystemicRisk()
	}
}

// ─── EVM Stack Benchmarks ────────────────────────────────────────────

func BenchmarkStack_PushPop(b *testing.B) {
	s := evm.NewStack()
	val := big.NewInt(42)

	b.ResetTimer()
	b.ReportAllocs()
	for i := 0; i < b.N; i++ {
		s.Push(val)
		s.Pop()
	}
}

func BenchmarkStack_Dup(b *testing.B) {
	s := evm.NewStack()
	s.Push(big.NewInt(42))

	b.ResetTimer()
	b.ReportAllocs()
	for i := 0; i < b.N; i++ {
		s.Dup(1)
		s.Pop()
	}
}

func BenchmarkStack_Swap(b *testing.B) {
	s := evm.NewStack()
	for i := 0; i < 16; i++ {
		s.Push(big.NewInt(int64(i)))
	}

	b.ResetTimer()
	b.ReportAllocs()
	for i := 0; i < b.N; i++ {
		s.Swap(1)
	}
}

// ─── EVM Memory Benchmarks ──────────────────────────────────────────

func BenchmarkMemory_Set32(b *testing.B) {
	mem := evm.NewMemory()
	mem.Resize(32) // pre-expand
	val := new(big.Int).SetBytes([]byte{0xFF, 0xAA, 0xBB, 0xCC})

	b.ResetTimer()
	b.ReportAllocs()
	for i := 0; i < b.N; i++ {
		_ = mem.Set32(0, val)
	}
}

func BenchmarkMemory_Resize(b *testing.B) {
	b.ResetTimer()
	b.ReportAllocs()
	for i := 0; i < b.N; i++ {
		mem := evm.NewMemory()
		_, _ = mem.Resize(4096)
	}
}

// ─── Helpers ─────────────────────────────────────────────────────────

func makeTestContextArgs(code []byte, gas uint64) (*evm.BlockContext, *evm.TxContext, *evm.CallContext) {
	block := &evm.BlockContext{
		GasLimit:    30_000_000,
		BlockNumber: 100,
		Timestamp:   1700000000,
		BaseFee:     big.NewInt(1_000_000_000),
		ChainID:     big.NewInt(3303),
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
		Code:    code,
		Gas:     gas,
	}
	return block, tx, call
}
