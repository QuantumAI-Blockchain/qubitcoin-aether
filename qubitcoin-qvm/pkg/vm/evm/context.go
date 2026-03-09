package evm

import (
	"math/big"
)

// BlockContext provides EVM block-level information.
type BlockContext struct {
	// Coinbase is the miner/validator address.
	Coinbase [20]byte
	// GasLimit is the block gas limit (default 30,000,000).
	GasLimit uint64
	// BlockNumber is the current block height.
	BlockNumber uint64
	// Timestamp is the block timestamp (unix seconds).
	Timestamp uint64
	// Difficulty / PrevRandao (post-merge this is prevRandao).
	PrevRandao [32]byte
	// BaseFee is the EIP-1559 base fee per gas.
	BaseFee *big.Int
	// ChainID is the chain identifier (3303 mainnet, 3304 testnet).
	ChainID *big.Int
}

// NewBlockContext creates a block context with Qubitcoin defaults.
func NewBlockContext() *BlockContext {
	return &BlockContext{
		GasLimit: 30_000_000,
		BaseFee:  new(big.Int),
		ChainID:  big.NewInt(3303),
	}
}

// TxContext provides EVM transaction-level information.
type TxContext struct {
	// Origin is the original sender of the transaction (tx.from).
	Origin [20]byte
	// GasPrice is the effective gas price for this transaction.
	GasPrice *big.Int
}

// CallContext holds per-call execution context (one per CALL/CREATE depth).
type CallContext struct {
	// Caller is the address that initiated this call.
	Caller [20]byte
	// Address is the address of the contract being executed.
	Address [20]byte
	// Value is the QBC value (wei) transferred with this call.
	Value *big.Int
	// Input is the calldata for this call.
	Input []byte
	// Code is the bytecode being executed.
	Code []byte
	// Gas is the gas limit for this call.
	Gas uint64
	// IsStatic is true for STATICCALL (no state modifications).
	IsStatic bool
	// Depth is the call depth (0 = top-level, max 1024).
	Depth int
}

// AccessSet tracks warm/cold address and storage slot accesses per EIP-2929.
type AccessSet struct {
	Addresses map[[20]byte]bool
	Slots     map[[20]byte]map[[32]byte]bool
}

// NewAccessSet creates a new empty access set.
func NewAccessSet() *AccessSet {
	return &AccessSet{
		Addresses: make(map[[20]byte]bool),
		Slots:     make(map[[20]byte]map[[32]byte]bool),
	}
}

// IsAddressWarm returns true if the address has been accessed this transaction.
func (as *AccessSet) IsAddressWarm(addr [20]byte) bool {
	return as.Addresses[addr]
}

// MarkAddressWarm marks an address as warm (accessed).
func (as *AccessSet) MarkAddressWarm(addr [20]byte) {
	as.Addresses[addr] = true
}

// IsSlotWarm returns true if the storage slot has been accessed this transaction.
func (as *AccessSet) IsSlotWarm(addr [20]byte, key [32]byte) bool {
	if slots, ok := as.Slots[addr]; ok {
		return slots[key]
	}
	return false
}

// MarkSlotWarm marks a storage slot as warm (accessed).
func (as *AccessSet) MarkSlotWarm(addr [20]byte, key [32]byte) {
	if _, ok := as.Slots[addr]; !ok {
		as.Slots[addr] = make(map[[32]byte]bool)
	}
	as.Slots[addr][key] = true
}

// ExecutionContext is the complete execution environment for a single call frame.
type ExecutionContext struct {
	Block *BlockContext
	Tx    *TxContext
	Call  *CallContext

	// VM state
	PC         uint64
	Stack      *Stack
	Memory     *Memory
	ReturnData []byte

	// Gas tracking
	GasUsed   uint64
	GasRefund uint64

	// Execution state
	Stopped  bool
	Reverted bool

	// Logs emitted during execution
	Logs []*Log

	// Valid JUMPDEST positions (pre-analyzed)
	ValidJumpdests map[uint64]bool

	// EIP-2929: Warm/cold access tracking
	AccessList *AccessSet

	// EIP-2200: Original storage values at transaction start
	// Used for accurate SSTORE gas calculation
	OriginalStorage map[[20]byte]map[[32]byte][32]byte
}

// Log represents an EVM log entry (event).
type Log struct {
	Address [20]byte
	Topics  [][32]byte
	Data    []byte
}

// NewExecutionContext creates a fully initialized execution context.
func NewExecutionContext(
	block *BlockContext,
	tx *TxContext,
	call *CallContext,
) *ExecutionContext {
	ctx := &ExecutionContext{
		Block:           block,
		Tx:              tx,
		Call:            call,
		Stack:           NewStack(),
		Memory:          NewMemory(),
		ValidJumpdests:  analyzeJumpdests(call.Code),
		AccessList:      NewAccessSet(),
		OriginalStorage: make(map[[20]byte]map[[32]byte][32]byte),
	}
	// Pre-warm the contract address and caller per EIP-2929
	ctx.AccessList.MarkAddressWarm(call.Address)
	ctx.AccessList.MarkAddressWarm(call.Caller)
	if tx != nil {
		ctx.AccessList.MarkAddressWarm(tx.Origin)
	}
	return ctx
}

// UseGas consumes gas. Returns false if insufficient gas.
func (ctx *ExecutionContext) UseGas(amount uint64) bool {
	newUsed := ctx.GasUsed + amount
	if newUsed > ctx.Call.Gas || newUsed < ctx.GasUsed {
		return false
	}
	ctx.GasUsed = newUsed
	return true
}

// GasRemaining returns the gas remaining for this call.
func (ctx *ExecutionContext) GasRemaining() uint64 {
	if ctx.GasUsed >= ctx.Call.Gas {
		return 0
	}
	return ctx.Call.Gas - ctx.GasUsed
}

// analyzeJumpdests pre-scans bytecode to find valid JUMPDEST positions.
// This prevents jumping into PUSH data.
func analyzeJumpdests(code []byte) map[uint64]bool {
	dests := make(map[uint64]bool)
	for i := 0; i < len(code); {
		op := Opcode(code[i])
		if op == JUMPDEST {
			dests[uint64(i)] = true
		}
		// Skip PUSH data bytes
		if op >= PUSH1 && op <= PUSH32 {
			pushSize := int(op-PUSH1) + 1
			i += pushSize
		}
		i++
	}
	return dests
}
