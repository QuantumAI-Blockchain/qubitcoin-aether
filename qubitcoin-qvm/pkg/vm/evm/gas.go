package evm

// Gas cost constants per the EVM specification (Berlin/Shanghai).
const (
	GasZero          uint64 = 0
	GasBase          uint64 = 2
	GasVeryLow       uint64 = 3
	GasLow           uint64 = 5
	GasMid           uint64 = 8
	GasHigh          uint64 = 10
	GasJumpdest      uint64 = 1
	GasExpByte       uint64 = 50
	GasKeccak256     uint64 = 30
	GasKeccak256Word uint64 = 6
	GasCopy          uint64 = 3
	GasCallStipend   uint64 = 2300
	GasSloadCold     uint64 = 2100
	GasSloadWarm     uint64 = 100
	GasSstoreCold    uint64 = 20000
	GasSstoreWarm    uint64 = 100
	GasSstoreClean   uint64 = 2900
	GasSstoreReset   uint64 = 2900
	GasSstoreRefund  uint64 = 4800
	GasBalance       uint64 = 2600
	GasExtCode       uint64 = 2600
	GasExtCodeHash   uint64 = 2600
	GasCall          uint64 = 100
	GasCallCold      uint64 = 2600
	GasCallWarm      uint64 = 100
	GasCallValue     uint64 = 9000
	GasCallNewAcct   uint64 = 25000
	GasCreate        uint64 = 32000
	GasCreate2       uint64 = 32000
	GasSelfDestruct  uint64 = 5000
	GasLog           uint64 = 375
	GasLogTopic      uint64 = 375
	GasLogData       uint64 = 8
	GasBlockhash     uint64 = 20
	GasCodeDeposit   uint64 = 200 // per byte

	// Limits
	MaxCodeSize     uint64 = 24576 // EIP-170: 24KB
	MaxInitCodeSize uint64 = 49152 // EIP-3860: 2 * 24KB
	MaxCallDepth    int    = 1024
	DefaultGasLimit uint64 = 30_000_000 // QBC block gas limit
)

// ConstGas maps opcodes to their constant (base) gas cost.
// Opcodes with dynamic costs are not in this map — they compute cost at execution time.
var ConstGas = map[Opcode]uint64{
	STOP: GasZero,

	// Arithmetic (GasVeryLow = 3)
	ADD:     GasVeryLow,
	SUB:     GasVeryLow,
	MUL:     GasLow,
	DIV:     GasLow,
	SDIV:    GasLow,
	MOD:     GasLow,
	SMOD:    GasLow,
	ADDMOD:  GasMid,
	MULMOD:  GasMid,
	SIGNEXT: GasLow,
	// EXP: base 10 + dynamic (50 per byte of exponent)
	EXP: GasHigh,

	// Comparison & Bitwise (GasVeryLow = 3)
	LT:     GasVeryLow,
	GT:     GasVeryLow,
	SLT:    GasVeryLow,
	SGT:    GasVeryLow,
	EQ:     GasVeryLow,
	ISZERO: GasVeryLow,
	AND:    GasVeryLow,
	OR:     GasVeryLow,
	XOR:    GasVeryLow,
	NOT:    GasVeryLow,
	BYTE:   GasVeryLow,
	SHL:    GasVeryLow,
	SHR:    GasVeryLow,
	SAR:    GasVeryLow,

	// Keccak (base 30 + dynamic per word)
	KECCAK256: GasKeccak256,

	// Environment info
	ADDRESS:   GasBase,
	ORIGIN:    GasBase,
	CALLER:    GasBase,
	CALLVALUE: GasBase,
	GASPRICE:  GasBase,
	COINBASE:  GasBase,
	TIMESTAMP: GasBase,
	NUMBER:    GasBase,
	PREVRANDAO: GasBase,
	GASLIMIT:  GasBase,
	CHAINID:   GasBase,

	CALLDATALOAD: GasVeryLow,
	CALLDATASIZE: GasBase,
	CALLDATACOPY: GasVeryLow, // base; + dynamic copy cost
	CODESIZE:     GasBase,
	CODECOPY:     GasVeryLow, // base; + dynamic copy cost
	RETURNDATASIZE: GasBase,
	RETURNDATACOPY: GasVeryLow, // base; + dynamic copy cost

	// Balance / ext code — cold access
	BALANCE:        GasBalance,
	SELFBALANCE:    GasLow,
	EXTCODESIZE:    GasExtCode,
	EXTCODECOPY:    GasExtCode,    // + dynamic copy cost
	EXTCODEHASH:    GasExtCodeHash,
	BASEFEE:        GasBase,

	// Block info
	BLOCKHASH: GasBlockhash,

	// Stack, Memory, Storage, Flow
	POP:     GasBase,
	MLOAD:   GasVeryLow, // + dynamic memory expansion
	MSTORE:  GasVeryLow, // + dynamic memory expansion
	MSTORE8: GasVeryLow, // + dynamic memory expansion
	SLOAD:   GasSloadWarm, // Base warm cost; cold surcharge added dynamically (EIP-2929)
	// SSTORE: dynamic (EIP-2200 / EIP-3529)
	JUMP:     GasMid,
	JUMPI:    GasHigh,
	PC:       GasBase,
	MSIZE:    GasBase,
	GAS:      GasBase,
	JUMPDEST: GasJumpdest,
	PUSH0:    GasBase,

	// Log opcodes (base; + dynamic per topic + data)
	LOG0: GasLog,
	LOG1: GasLog,
	LOG2: GasLog,
	LOG3: GasLog,
	LOG4: GasLog,

	// System opcodes
	RETURN: GasZero,
	REVERT: GasZero,
	INVALID: GasZero,
}

// PushGas returns the gas cost for PUSH1-PUSH32 (all cost GasVeryLow).
func PushGas() uint64 {
	return GasVeryLow
}

// DupGas returns the gas cost for DUP1-DUP16.
func DupGas() uint64 {
	return GasVeryLow
}

// SwapGas returns the gas cost for SWAP1-SWAP16.
func SwapGas() uint64 {
	return GasVeryLow
}

// LogGasCost computes the full gas cost for LOG0-LOG4.
//
//	gas = 375 + 375 * numTopics + 8 * dataSize + memExpansionCost
func LogGasCost(numTopics int, dataSize uint64) uint64 {
	return GasLog + GasLogTopic*uint64(numTopics) + GasLogData*dataSize
}

// Keccak256GasCost computes the full gas cost for KECCAK256.
//
//	gas = 30 + 6 * ceil(size / 32)
func Keccak256GasCost(size uint64) uint64 {
	words := (size + 31) / 32
	return GasKeccak256 + GasKeccak256Word*words
}

// CopyGasCost computes the dynamic copy cost for CALLDATACOPY/CODECOPY/RETURNDATACOPY.
//
//	gas = 3 * ceil(size / 32) + memExpansionCost
func CopyGasCost(size uint64) uint64 {
	words := (size + 31) / 32
	return GasCopy * words
}

// ExpGasCost computes the dynamic gas cost for EXP.
//
//	gas = 10 + 50 * byteSize(exponent)
func ExpGasCost(expByteLen uint64) uint64 {
	return GasHigh + GasExpByte*expByteLen
}

// SstoreGasCost represents the gas result of an SSTORE operation (EIP-2200).
type SstoreGasCost struct {
	Cost   uint64
	Refund int64
}

// CalcSstoreGas computes SSTORE gas per EIP-2200 / EIP-3529.
//
//	current: value currently in storage
//	new_: value being written
//	original: value at the start of the transaction
//	cold: whether this is first access to the slot
func CalcSstoreGas(currentIsZero, newIsZero, currentEqualsNew, originalIsZero, cold bool) SstoreGasCost {
	var baseCost uint64
	if cold {
		baseCost = GasSloadCold
	}

	// No-op: current == new
	if currentEqualsNew {
		return SstoreGasCost{Cost: GasSloadWarm + baseCost, Refund: 0}
	}

	// Fresh write: original is zero, current is zero, writing non-zero
	if originalIsZero {
		return SstoreGasCost{Cost: GasSstoreCold + baseCost, Refund: 0}
	}

	// Reset: writing back to original
	var refund int64
	if newIsZero && !currentIsZero {
		refund = int64(GasSstoreRefund)
	}

	return SstoreGasCost{Cost: GasSstoreReset + baseCost, Refund: refund}
}
