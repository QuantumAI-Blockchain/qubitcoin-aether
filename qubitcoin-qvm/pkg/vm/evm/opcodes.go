// Package evm implements the EVM-compatible bytecode interpreter.
//
// This package provides the core execution engine for standard EVM opcodes
// (0x00-0x9F, 0xA0-0xA4, 0xF0-0xFF) with full gas accounting, stack/memory/storage
// management, and precompiled contract support.
//
// The QVM extends this with quantum opcodes in pkg/vm/quantum/.
package evm

// Opcode represents an EVM opcode byte.
type Opcode byte

// Standard EVM opcodes.
const (
	// Arithmetic
	STOP    Opcode = 0x00
	ADD     Opcode = 0x01
	MUL     Opcode = 0x02
	SUB     Opcode = 0x03
	DIV     Opcode = 0x04
	SDIV    Opcode = 0x05
	MOD     Opcode = 0x06
	SMOD    Opcode = 0x07
	ADDMOD  Opcode = 0x08
	MULMOD  Opcode = 0x09
	EXP     Opcode = 0x0A
	SIGNEXT Opcode = 0x0B

	// Comparison & Bitwise
	LT     Opcode = 0x10
	GT     Opcode = 0x11
	SLT    Opcode = 0x12
	SGT    Opcode = 0x13
	EQ     Opcode = 0x14
	ISZERO Opcode = 0x15
	AND    Opcode = 0x16
	OR     Opcode = 0x17
	XOR    Opcode = 0x18
	NOT    Opcode = 0x19
	BYTE   Opcode = 0x1A
	SHL    Opcode = 0x1B
	SHR    Opcode = 0x1C
	SAR    Opcode = 0x1D

	// Keccak
	KECCAK256 Opcode = 0x20

	// Environment
	ADDRESS        Opcode = 0x30
	BALANCE        Opcode = 0x31
	ORIGIN         Opcode = 0x32
	CALLER         Opcode = 0x33
	CALLVALUE      Opcode = 0x34
	CALLDATALOAD   Opcode = 0x35
	CALLDATASIZE   Opcode = 0x36
	CALLDATACOPY   Opcode = 0x37
	CODESIZE       Opcode = 0x38
	CODECOPY       Opcode = 0x39
	GASPRICE       Opcode = 0x3A
	EXTCODESIZE    Opcode = 0x3B
	EXTCODECOPY    Opcode = 0x3C
	RETURNDATASIZE Opcode = 0x3D
	RETURNDATACOPY Opcode = 0x3E
	EXTCODEHASH    Opcode = 0x3F

	// Block Info
	BLOCKHASH   Opcode = 0x40
	COINBASE    Opcode = 0x41
	TIMESTAMP   Opcode = 0x42
	NUMBER      Opcode = 0x43
	PREVRANDAO  Opcode = 0x44
	GASLIMIT    Opcode = 0x45
	CHAINID     Opcode = 0x46
	SELFBALANCE Opcode = 0x47
	BASEFEE     Opcode = 0x48

	// Stack, Memory, Storage, Flow
	POP      Opcode = 0x50
	MLOAD    Opcode = 0x51
	MSTORE   Opcode = 0x52
	MSTORE8  Opcode = 0x53
	SLOAD    Opcode = 0x54
	SSTORE   Opcode = 0x55
	JUMP     Opcode = 0x56
	JUMPI    Opcode = 0x57
	PC       Opcode = 0x58
	MSIZE    Opcode = 0x59
	GAS      Opcode = 0x5A
	JUMPDEST Opcode = 0x5B

	// Push
	PUSH0  Opcode = 0x5F
	PUSH1  Opcode = 0x60
	PUSH32 Opcode = 0x7F

	// Dup
	DUP1  Opcode = 0x80
	DUP16 Opcode = 0x8F

	// Swap
	SWAP1  Opcode = 0x90
	SWAP16 Opcode = 0x9F

	// Log
	LOG0 Opcode = 0xA0
	LOG1 Opcode = 0xA1
	LOG2 Opcode = 0xA2
	LOG3 Opcode = 0xA3
	LOG4 Opcode = 0xA4

	// System
	CREATE       Opcode = 0xF0
	CALL         Opcode = 0xF1
	CALLCODE     Opcode = 0xF2
	RETURN       Opcode = 0xF3
	DELEGATECALL Opcode = 0xF4
	CREATE2      Opcode = 0xF5
	STATICCALL   Opcode = 0xFA
	REVERT       Opcode = 0xFD
	INVALID      Opcode = 0xFE
	SELFDESTRUCT Opcode = 0xFF
)

// GasCost maps opcodes to their base gas costs.
var GasCost = map[Opcode]uint64{
	STOP: 0, ADD: 3, MUL: 5, SUB: 3, DIV: 5,
	SDIV: 5, MOD: 5, SMOD: 5, ADDMOD: 8, MULMOD: 8,
	EXP: 10, SIGNEXT: 5,
	LT: 3, GT: 3, SLT: 3, SGT: 3, EQ: 3,
	ISZERO: 3, AND: 3, OR: 3, XOR: 3, NOT: 3,
	BYTE: 3, SHL: 3, SHR: 3, SAR: 3,
	KECCAK256: 30,
	ADDRESS: 2, BALANCE: 2600, ORIGIN: 2, CALLER: 2,
	CALLVALUE: 2, CALLDATALOAD: 3, CALLDATASIZE: 2, CALLDATACOPY: 3,
	CODESIZE: 2, CODECOPY: 3, GASPRICE: 2,
	POP: 2, MLOAD: 3, MSTORE: 3, MSTORE8: 3,
	SLOAD: 2100,
	// SSTORE uses dynamic gas via CalcSstoreGas() — no flat cost here.
	JUMP: 8, JUMPI: 10, PC: 2, MSIZE: 2, GAS: 2, JUMPDEST: 1,
}
