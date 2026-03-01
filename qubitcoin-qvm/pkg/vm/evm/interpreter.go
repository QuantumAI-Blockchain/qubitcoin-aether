package evm

import (
	"fmt"
	"log"
	"math/big"

	"golang.org/x/crypto/sha3"
)

// ExecutionResult holds the outcome of bytecode execution.
type ExecutionResult struct {
	Success      bool
	ReturnData   []byte
	GasUsed      uint64
	GasRemaining uint64
	GasRefund    uint64
	Logs         []*Log
	RevertReason string
	Err          error
}

// StateAccessor abstracts storage operations so the interpreter
// can be tested and used without a real database.
type StateAccessor interface {
	GetStorage(addr [20]byte, key [32]byte) [32]byte
	SetStorage(addr [20]byte, key [32]byte, val [32]byte)
	GetBalance(addr [20]byte) *big.Int
	SetBalance(addr [20]byte, balance *big.Int)
	GetCodeHash(addr [20]byte) [32]byte
	GetCode(addr [20]byte) []byte
	GetCodeSize(addr [20]byte) uint64
	SetCode(addr [20]byte, code []byte)
	GetBlockHash(num uint64) [32]byte
	AccountExists(addr [20]byte) bool
	CreateAccount(addr [20]byte)
	GetNonce(addr [20]byte) uint64
	SetNonce(addr [20]byte, nonce uint64)
	Snapshot() int
	RevertToSnapshot(id int)
}

// Interpreter is the QVM EVM bytecode interpreter.
type Interpreter struct {
	state  StateAccessor
	config *InterpreterConfig
}

// InterpreterConfig holds configurable interpreter parameters.
type InterpreterConfig struct {
	// MaxCallDepth is the maximum call depth (default 1024).
	MaxCallDepth int
	// BlockGasLimit is the block gas limit (default 30,000,000).
	BlockGasLimit uint64
}

// DefaultConfig returns the default interpreter configuration.
func DefaultConfig() *InterpreterConfig {
	return &InterpreterConfig{
		MaxCallDepth:  MaxCallDepth,
		BlockGasLimit: DefaultGasLimit,
	}
}

// NewInterpreter creates a new EVM interpreter.
func NewInterpreter(state StateAccessor, config *InterpreterConfig) *Interpreter {
	if config == nil {
		config = DefaultConfig()
	}
	return &Interpreter{
		state:  state,
		config: config,
	}
}

// Execute runs bytecode and returns the execution result.
func (interp *Interpreter) Execute(
	block *BlockContext,
	tx *TxContext,
	call *CallContext,
) *ExecutionResult {
	if call.Depth > interp.config.MaxCallDepth {
		return &ExecutionResult{
			Success:      false,
			RevertReason: "max call depth exceeded",
			GasUsed:      call.Gas,
		}
	}

	ctx := NewExecutionContext(block, tx, call)
	result := &ExecutionResult{}

	err := interp.run(ctx)

	result.GasUsed = ctx.GasUsed
	result.GasRemaining = ctx.GasRemaining()
	result.GasRefund = ctx.GasRefund
	result.Logs = ctx.Logs
	result.ReturnData = ctx.ReturnData

	if err != nil {
		result.Success = false
		result.RevertReason = err.Error()
		result.Err = err
		if ctx.Reverted {
			// REVERT preserves return data
			result.ReturnData = ctx.ReturnData
		}
	} else {
		result.Success = !ctx.Reverted
		if ctx.Reverted {
			result.RevertReason = "execution reverted"
		}
	}

	return result
}

// run is the main execution loop.
func (interp *Interpreter) run(ctx *ExecutionContext) error {
	code := ctx.Call.Code

	for ctx.PC < uint64(len(code)) && !ctx.Stopped && !ctx.Reverted {
		op := Opcode(code[ctx.PC])

		// Charge constant gas first (dynamic costs charged in-handler)
		if cost, ok := ConstGas[op]; ok {
			if !ctx.UseGas(cost) {
				return fmt.Errorf("out of gas at PC=%d op=0x%02x", ctx.PC, op)
			}
		}

		var err error

		switch {
		// ════════════════════════════════════════════════════════════════
		// STOP
		// ════════════════════════════════════════════════════════════════
		case op == STOP:
			ctx.Stopped = true

		// ════════════════════════════════════════════════════════════════
		// ARITHMETIC
		// ════════════════════════════════════════════════════════════════
		case op == ADD:
			a, b := mustPop2(ctx)
			err = ctx.Stack.Push(U256(new(big.Int).Add(a, b)))

		case op == MUL:
			a, b := mustPop2(ctx)
			err = ctx.Stack.Push(U256(new(big.Int).Mul(a, b)))

		case op == SUB:
			a, b := mustPop2(ctx)
			err = ctx.Stack.Push(U256(new(big.Int).Sub(a, b)))

		case op == DIV:
			a, b := mustPop2(ctx)
			if b.Sign() == 0 {
				err = ctx.Stack.Push(big.NewInt(0))
			} else {
				err = ctx.Stack.Push(new(big.Int).Div(a, b))
			}

		case op == SDIV:
			a, b := mustPop2(ctx)
			if b.Sign() == 0 {
				err = ctx.Stack.Push(big.NewInt(0))
			} else {
				sa, sb := ToSignedBig(a), ToSignedBig(b)
				result := new(big.Int).Quo(sa, sb)
				err = ctx.Stack.Push(ToUnsignedBig(result))
			}

		case op == MOD:
			a, b := mustPop2(ctx)
			if b.Sign() == 0 {
				err = ctx.Stack.Push(big.NewInt(0))
			} else {
				err = ctx.Stack.Push(new(big.Int).Mod(a, b))
			}

		case op == SMOD:
			a, b := mustPop2(ctx)
			if b.Sign() == 0 {
				err = ctx.Stack.Push(big.NewInt(0))
			} else {
				sa, sb := ToSignedBig(a), ToSignedBig(b)
				result := new(big.Int).Rem(sa, sb)
				err = ctx.Stack.Push(ToUnsignedBig(result))
			}

		case op == ADDMOD:
			a, b, n := mustPop3(ctx)
			if n.Sign() == 0 {
				err = ctx.Stack.Push(big.NewInt(0))
			} else {
				sum := new(big.Int).Add(a, b)
				err = ctx.Stack.Push(sum.Mod(sum, n))
			}

		case op == MULMOD:
			a, b, n := mustPop3(ctx)
			if n.Sign() == 0 {
				err = ctx.Stack.Push(big.NewInt(0))
			} else {
				prod := new(big.Int).Mul(a, b)
				err = ctx.Stack.Push(prod.Mod(prod, n))
			}

		case op == EXP:
			base, exp := mustPop2(ctx)
			// Dynamic gas: 50 per byte of exponent
			expBytes := uint64((exp.BitLen() + 7) / 8)
			if !ctx.UseGas(GasExpByte * expBytes) {
				return fmt.Errorf("out of gas: EXP dynamic cost")
			}
			if exp.Sign() == 0 {
				err = ctx.Stack.Push(big.NewInt(1))
			} else {
				result := new(big.Int).Exp(base, exp, uint256Mod)
				err = ctx.Stack.Push(result)
			}

		case op == SIGNEXT:
			b, x := mustPop2(ctx)
			if b.Cmp(big.NewInt(31)) < 0 {
				bit := b.Uint64()*8 + 7
				signBit := new(big.Int).Lsh(big1, uint(bit))
				mask := new(big.Int).Sub(signBit, big1)
				if x.Bit(int(bit)) == 1 {
					// Negative: set all high bits
					err = ctx.Stack.Push(U256(new(big.Int).Or(x, new(big.Int).Xor(maxUint256, mask))))
				} else {
					err = ctx.Stack.Push(new(big.Int).And(x, mask))
				}
			} else {
				err = ctx.Stack.Push(x)
			}

		// ════════════════════════════════════════════════════════════════
		// COMPARISON & BITWISE
		// ════════════════════════════════════════════════════════════════
		case op == LT:
			a, b := mustPop2(ctx)
			err = pushBool(ctx, a.Cmp(b) < 0)

		case op == GT:
			a, b := mustPop2(ctx)
			err = pushBool(ctx, a.Cmp(b) > 0)

		case op == SLT:
			a, b := mustPop2(ctx)
			sa, sb := ToSignedBig(a), ToSignedBig(b)
			err = pushBool(ctx, sa.Cmp(sb) < 0)

		case op == SGT:
			a, b := mustPop2(ctx)
			sa, sb := ToSignedBig(a), ToSignedBig(b)
			err = pushBool(ctx, sa.Cmp(sb) > 0)

		case op == EQ:
			a, b := mustPop2(ctx)
			err = pushBool(ctx, a.Cmp(b) == 0)

		case op == ISZERO:
			a := mustPop1(ctx)
			err = pushBool(ctx, a.Sign() == 0)

		case op == AND:
			a, b := mustPop2(ctx)
			err = ctx.Stack.Push(new(big.Int).And(a, b))

		case op == OR:
			a, b := mustPop2(ctx)
			err = ctx.Stack.Push(new(big.Int).Or(a, b))

		case op == XOR:
			a, b := mustPop2(ctx)
			err = ctx.Stack.Push(new(big.Int).Xor(a, b))

		case op == NOT:
			a := mustPop1(ctx)
			err = ctx.Stack.Push(new(big.Int).Xor(a, maxUint256))

		case op == BYTE:
			i, x := mustPop2(ctx)
			if i.Cmp(big.NewInt(32)) < 0 {
				shift := uint((31 - i.Uint64()) * 8)
				result := new(big.Int).Rsh(x, shift)
				result.And(result, big.NewInt(0xFF))
				err = ctx.Stack.Push(result)
			} else {
				err = ctx.Stack.Push(big.NewInt(0))
			}

		case op == SHL:
			shift, val := mustPop2(ctx)
			if shift.Cmp(big256) >= 0 {
				err = ctx.Stack.Push(big.NewInt(0))
			} else {
				err = ctx.Stack.Push(U256(new(big.Int).Lsh(val, uint(shift.Uint64()))))
			}

		case op == SHR:
			shift, val := mustPop2(ctx)
			if shift.Cmp(big256) >= 0 {
				err = ctx.Stack.Push(big.NewInt(0))
			} else {
				err = ctx.Stack.Push(new(big.Int).Rsh(val, uint(shift.Uint64())))
			}

		case op == SAR:
			shift, val := mustPop2(ctx)
			sval := ToSignedBig(val)
			if shift.Cmp(big256) >= 0 {
				if sval.Sign() < 0 {
					err = ctx.Stack.Push(new(big.Int).Set(maxUint256))
				} else {
					err = ctx.Stack.Push(big.NewInt(0))
				}
			} else {
				result := new(big.Int).Rsh(sval, uint(shift.Uint64()))
				err = ctx.Stack.Push(ToUnsignedBig(result))
			}

		// ════════════════════════════════════════════════════════════════
		// KECCAK256
		// ════════════════════════════════════════════════════════════════
		case op == KECCAK256:
			offset, size := mustPop2(ctx)
			off, sz := offset.Uint64(), size.Uint64()
			// Memory expansion + dynamic gas
			memCost := ctx.Memory.Resize(off + sz)
			wordCost := Keccak256GasCost(sz) - GasKeccak256 // subtract base (already charged)
			if !ctx.UseGas(memCost + wordCost) {
				return fmt.Errorf("out of gas: KECCAK256")
			}
			data := ctx.Memory.Get(off, sz)
			h := sha3.NewLegacyKeccak256()
			h.Write(data)
			hash := h.Sum(nil)
			err = ctx.Stack.Push(new(big.Int).SetBytes(hash))

		// ════════════════════════════════════════════════════════════════
		// ENVIRONMENT
		// ════════════════════════════════════════════════════════════════
		case op == ADDRESS:
			err = ctx.Stack.Push(new(big.Int).SetBytes(ctx.Call.Address[:]))

		case op == BALANCE:
			addrInt := mustPop1(ctx)
			var addr [20]byte
			safeAddrBytes(addrInt, &addr)
			balance := big.NewInt(0)
			if interp.state != nil {
				balance = interp.state.GetBalance(addr)
			}
			err = ctx.Stack.Push(balance)

		case op == ORIGIN:
			err = ctx.Stack.Push(new(big.Int).SetBytes(ctx.Tx.Origin[:]))

		case op == CALLER:
			err = ctx.Stack.Push(new(big.Int).SetBytes(ctx.Call.Caller[:]))

		case op == CALLVALUE:
			val := big.NewInt(0)
			if ctx.Call.Value != nil {
				val = ctx.Call.Value
			}
			err = ctx.Stack.Push(new(big.Int).Set(val))

		case op == CALLDATALOAD:
			offset := mustPop1(ctx)
			off := offset.Uint64()
			var data [32]byte
			input := ctx.Call.Input
			for i := 0; i < 32; i++ {
				idx := off + uint64(i)
				if idx < uint64(len(input)) {
					data[i] = input[idx]
				}
			}
			err = ctx.Stack.Push(new(big.Int).SetBytes(data[:]))

		case op == CALLDATASIZE:
			err = ctx.Stack.PushUint64(uint64(len(ctx.Call.Input)))

		case op == CALLDATACOPY:
			err = interp.opCopy(ctx, ctx.Call.Input)

		case op == CODESIZE:
			err = ctx.Stack.PushUint64(uint64(len(ctx.Call.Code)))

		case op == CODECOPY:
			err = interp.opCopy(ctx, ctx.Call.Code)

		case op == GASPRICE:
			price := big.NewInt(0)
			if ctx.Tx.GasPrice != nil {
				price = ctx.Tx.GasPrice
			}
			err = ctx.Stack.Push(new(big.Int).Set(price))

		case op == EXTCODESIZE:
			addrInt := mustPop1(ctx)
			var addr [20]byte
			safeAddrBytes(addrInt, &addr)
			var sz uint64
			if interp.state != nil {
				sz = interp.state.GetCodeSize(addr)
			}
			err = ctx.Stack.PushUint64(sz)

		case op == EXTCODECOPY:
			addrInt := mustPop1(ctx)
			destOff, codeOff, size := mustPop3(ctx)
			var addr [20]byte
			safeAddrBytes(addrInt, &addr)
			var extCode []byte
			if interp.state != nil {
				extCode = interp.state.GetCode(addr)
			}
			sz := size.Uint64()
			// Dynamic copy cost + memory expansion
			copyCost := CopyGasCost(sz)
			memCost := ctx.Memory.Resize(destOff.Uint64() + sz)
			if !ctx.UseGas(copyCost + memCost) {
				return fmt.Errorf("out of gas: EXTCODECOPY")
			}
			data := padRight(sliceBytes(extCode, codeOff.Uint64(), sz), int(sz))
			ctx.Memory.Set(destOff.Uint64(), data)

		case op == RETURNDATASIZE:
			err = ctx.Stack.PushUint64(uint64(len(ctx.ReturnData)))

		case op == RETURNDATACOPY:
			destOff, off, size := mustPop3(ctx)
			sz := size.Uint64()
			offVal := off.Uint64()
			if offVal+sz > uint64(len(ctx.ReturnData)) {
				return fmt.Errorf("return data out of bounds")
			}
			copyCost := CopyGasCost(sz)
			memCost := ctx.Memory.Resize(destOff.Uint64() + sz)
			if !ctx.UseGas(copyCost + memCost) {
				return fmt.Errorf("out of gas: RETURNDATACOPY")
			}
			ctx.Memory.Set(destOff.Uint64(), ctx.ReturnData[offVal:offVal+sz])

		case op == EXTCODEHASH:
			addrInt := mustPop1(ctx)
			var addr [20]byte
			safeAddrBytes(addrInt, &addr)
			hash := [32]byte{}
			if interp.state != nil {
				hash = interp.state.GetCodeHash(addr)
			}
			err = ctx.Stack.Push(new(big.Int).SetBytes(hash[:]))

		// ════════════════════════════════════════════════════════════════
		// BLOCK INFO
		// ════════════════════════════════════════════════════════════════
		case op == BLOCKHASH:
			num := mustPop1(ctx)
			blockNum := num.Uint64()
			hash := [32]byte{}
			if interp.state != nil && blockNum < ctx.Block.BlockNumber && blockNum >= ctx.Block.BlockNumber-256 {
				hash = interp.state.GetBlockHash(blockNum)
			}
			err = ctx.Stack.Push(new(big.Int).SetBytes(hash[:]))

		case op == COINBASE:
			err = ctx.Stack.Push(new(big.Int).SetBytes(ctx.Block.Coinbase[:]))

		case op == TIMESTAMP:
			err = ctx.Stack.PushUint64(ctx.Block.Timestamp)

		case op == NUMBER:
			err = ctx.Stack.PushUint64(ctx.Block.BlockNumber)

		case op == PREVRANDAO:
			err = ctx.Stack.Push(new(big.Int).SetBytes(ctx.Block.PrevRandao[:]))

		case op == GASLIMIT:
			err = ctx.Stack.PushUint64(ctx.Block.GasLimit)

		case op == CHAINID:
			chainID := big.NewInt(3301) // default QBC mainnet
			if ctx.Block.ChainID != nil {
				chainID = ctx.Block.ChainID
			}
			err = ctx.Stack.Push(new(big.Int).Set(chainID))

		case op == SELFBALANCE:
			balance := big.NewInt(0)
			if interp.state != nil {
				balance = interp.state.GetBalance(ctx.Call.Address)
			}
			err = ctx.Stack.Push(balance)

		case op == BASEFEE:
			baseFee := big.NewInt(0)
			if ctx.Block.BaseFee != nil {
				baseFee = ctx.Block.BaseFee
			}
			err = ctx.Stack.Push(new(big.Int).Set(baseFee))

		// ════════════════════════════════════════════════════════════════
		// STACK / MEMORY / STORAGE / FLOW
		// ════════════════════════════════════════════════════════════════
		case op == POP:
			_, err = ctx.Stack.Pop()

		case op == MLOAD:
			offset := mustPop1(ctx)
			off := offset.Uint64()
			memCost := ctx.Memory.Resize(off + 32)
			if !ctx.UseGas(memCost) {
				return fmt.Errorf("out of gas: MLOAD")
			}
			data := ctx.Memory.Get(off, 32)
			err = ctx.Stack.Push(new(big.Int).SetBytes(data))

		case op == MSTORE:
			offset, val := mustPop2(ctx)
			off := offset.Uint64()
			memCost := ctx.Memory.Resize(off + 32)
			if !ctx.UseGas(memCost) {
				return fmt.Errorf("out of gas: MSTORE")
			}
			ctx.Memory.Set32(off, val)

		case op == MSTORE8:
			offset, val := mustPop2(ctx)
			off := offset.Uint64()
			memCost := ctx.Memory.Resize(off + 1)
			if !ctx.UseGas(memCost) {
				return fmt.Errorf("out of gas: MSTORE8")
			}
			ctx.Memory.SetByte(off, byte(val.Uint64()&0xFF))

		case op == SLOAD:
			keyInt := mustPop1(ctx)
			var key [32]byte
			safeFillBytes(keyInt, key[:])

			// EIP-2929: Charge cold access surcharge for first-time slot access
			if !ctx.AccessList.IsSlotWarm(ctx.Call.Address, key) {
				ctx.AccessList.MarkSlotWarm(ctx.Call.Address, key)
				// Cold access: additional cost = 2100 - 100 (base already charged)
				if !ctx.UseGas(GasSloadCold - GasSloadWarm) {
					return fmt.Errorf("out of gas: SLOAD cold access")
				}
			}

			val := [32]byte{}
			if interp.state != nil {
				val = interp.state.GetStorage(ctx.Call.Address, key)
			}
			err = ctx.Stack.Push(new(big.Int).SetBytes(val[:]))

		case op == SSTORE:
			if ctx.Call.IsStatic {
				return fmt.Errorf("SSTORE in static context")
			}
			keyInt, valInt := mustPop2(ctx)
			var key, val [32]byte
			safeFillBytes(keyInt, key[:])
			safeFillBytes(valInt, val[:])

			// EIP-2200/EIP-2929 dynamic gas with warm/cold and original value tracking
			if interp.state != nil {
				current := interp.state.GetStorage(ctx.Call.Address, key)
				currentIsZero := current == [32]byte{}
				newIsZero := val == [32]byte{}
				currentEqualsNew := current == val

				// EIP-2200: Track original value at transaction start
				addr := ctx.Call.Address
				if _, ok := ctx.OriginalStorage[addr]; !ok {
					ctx.OriginalStorage[addr] = make(map[[32]byte][32]byte)
				}
				if _, ok := ctx.OriginalStorage[addr][key]; !ok {
					// First access to this slot in this tx — record original
					ctx.OriginalStorage[addr][key] = current
				}
				original := ctx.OriginalStorage[addr][key]
				originalIsZero := original == [32]byte{}

				// EIP-2929: Check warm/cold access for storage slot
				cold := !ctx.AccessList.IsSlotWarm(addr, key)
				ctx.AccessList.MarkSlotWarm(addr, key)

				result := CalcSstoreGas(currentIsZero, newIsZero, currentEqualsNew, originalIsZero, cold)
				if !ctx.UseGas(result.Cost) {
					return fmt.Errorf("out of gas: SSTORE")
				}
				if result.Refund > 0 {
					ctx.GasRefund += uint64(result.Refund)
				}
				interp.state.SetStorage(ctx.Call.Address, key, val)
			}

		case op == JUMP:
			dest := mustPop1(ctx)
			target := dest.Uint64()
			if !ctx.ValidJumpdests[target] {
				return fmt.Errorf("invalid JUMP destination: %d", target)
			}
			ctx.PC = target
			continue // Don't increment PC

		case op == JUMPI:
			dest, cond := mustPop2(ctx)
			if cond.Sign() != 0 {
				target := dest.Uint64()
				if !ctx.ValidJumpdests[target] {
					return fmt.Errorf("invalid JUMPI destination: %d", target)
				}
				ctx.PC = target
				continue
			}

		case op == PC:
			err = ctx.Stack.PushUint64(ctx.PC)

		case op == MSIZE:
			err = ctx.Stack.PushUint64(uint64(ctx.Memory.Len()))

		case op == GAS:
			err = ctx.Stack.PushUint64(ctx.GasRemaining())

		case op == JUMPDEST:
			// Marker only, gas already charged

		// ════════════════════════════════════════════════════════════════
		// PUSH
		// ════════════════════════════════════════════════════════════════
		case op == PUSH0:
			// Gas already charged via ConstGas[PUSH0] = GasBase
			err = ctx.Stack.Push(big.NewInt(0))

		case op >= PUSH1 && op <= PUSH32:
			if !ctx.UseGas(PushGas()) {
				return fmt.Errorf("out of gas: PUSH")
			}
			numBytes := int(op - PUSH1 + 1)
			start := ctx.PC + 1
			end := start + uint64(numBytes)
			var pushData []byte
			if end <= uint64(len(code)) {
				pushData = code[start:end]
			} else {
				// Pad with zeros if bytecode is shorter
				pushData = make([]byte, numBytes)
				avail := uint64(len(code)) - start
				if avail > 0 && start < uint64(len(code)) {
					copy(pushData, code[start:start+avail])
				}
			}
			err = ctx.Stack.Push(new(big.Int).SetBytes(pushData))
			ctx.PC += uint64(numBytes)

		// ════════════════════════════════════════════════════════════════
		// DUP
		// ════════════════════════════════════════════════════════════════
		case op >= DUP1 && op <= DUP16:
			if !ctx.UseGas(DupGas()) {
				return fmt.Errorf("out of gas: DUP")
			}
			depth := int(op-DUP1) + 1
			err = ctx.Stack.Dup(depth)

		// ════════════════════════════════════════════════════════════════
		// SWAP
		// ════════════════════════════════════════════════════════════════
		case op >= SWAP1 && op <= SWAP16:
			if !ctx.UseGas(SwapGas()) {
				return fmt.Errorf("out of gas: SWAP")
			}
			depth := int(op-SWAP1) + 1
			err = ctx.Stack.Swap(depth)

		// ════════════════════════════════════════════════════════════════
		// LOG
		// ════════════════════════════════════════════════════════════════
		case op >= LOG0 && op <= LOG4:
			if ctx.Call.IsStatic {
				return fmt.Errorf("LOG in static context")
			}
			numTopics := int(op - LOG0)
			offset, size := mustPop2(ctx)
			off, sz := offset.Uint64(), size.Uint64()

			topics := make([][32]byte, numTopics)
			for i := 0; i < numTopics; i++ {
				t := mustPop1(ctx)
				safeFillBytes(t, topics[i][:])
			}

			// Dynamic gas: 375 per topic + 8 per byte of data
			dynGas := LogGasCost(numTopics, sz) - GasLog // subtract base
			memCost := ctx.Memory.Resize(off + sz)
			if !ctx.UseGas(dynGas + memCost) {
				return fmt.Errorf("out of gas: LOG")
			}

			data := ctx.Memory.Get(off, sz)
			log := &Log{
				Address: ctx.Call.Address,
				Topics:  topics,
				Data:    data,
			}
			ctx.Logs = append(ctx.Logs, log)

		// ════════════════════════════════════════════════════════════════
		// SYSTEM
		// ════════════════════════════════════════════════════════════════
		case op == RETURN:
			offset, size := mustPop2(ctx)
			off, sz := offset.Uint64(), size.Uint64()
			memCost := ctx.Memory.Resize(off + sz)
			if !ctx.UseGas(memCost) {
				return fmt.Errorf("out of gas: RETURN")
			}
			ctx.ReturnData = ctx.Memory.Get(off, sz)
			ctx.Stopped = true

		case op == REVERT:
			offset, size := mustPop2(ctx)
			off, sz := offset.Uint64(), size.Uint64()
			memCost := ctx.Memory.Resize(off + sz)
			if !ctx.UseGas(memCost) {
				return fmt.Errorf("out of gas: REVERT")
			}
			ctx.ReturnData = ctx.Memory.Get(off, sz)
			ctx.Reverted = true
			ctx.Stopped = true

		case op == INVALID:
			return fmt.Errorf("invalid opcode 0xFE at PC=%d", ctx.PC)

		// ════════════════════════════════════════════════════════════════
		// SYSTEM: CREATE, CALL — full sub-call support
		// ════════════════════════════════════════════════════════════════
		case op == CREATE || op == CREATE2:
			if ctx.Call.IsStatic {
				return fmt.Errorf("CREATE in static context")
			}
			val, offset, size := mustPop3(ctx)
			var salt *big.Int
			if op == CREATE2 {
				salt = mustPop1(ctx)
			}
			off, sz := offset.Uint64(), size.Uint64()

			// Memory expansion + CREATE base gas
			memCost := ctx.Memory.Resize(off + sz)
			createGas := GasCreate
			if op == CREATE2 {
				// CREATE2 extra: 6 * ceil(len / 32) for keccak of init code
				createGas += GasKeccak256Word * ((sz + 31) / 32)
			}
			if !ctx.UseGas(memCost + createGas) {
				return fmt.Errorf("out of gas: CREATE")
			}

			if interp.state == nil {
				err = ctx.Stack.Push(big.NewInt(0))
				break
			}

			initCode := ctx.Memory.Get(off, sz)
			if uint64(len(initCode)) > MaxInitCodeSize {
				err = ctx.Stack.Push(big.NewInt(0))
				break
			}

			// Compute new contract address
			var newAddr [20]byte
			callerNonce := interp.state.GetNonce(ctx.Call.Address)
			if op == CREATE {
				// CREATE: address = keccak256(rlp([sender, nonce]))[12:]
				h := sha3.NewLegacyKeccak256()
				h.Write(ctx.Call.Address[:])
				nonceBytes := new(big.Int).SetUint64(callerNonce).Bytes()
				h.Write(nonceBytes)
				copy(newAddr[:], h.Sum(nil)[12:])
			} else {
				// CREATE2: address = keccak256(0xff ++ sender ++ salt ++ keccak256(init_code))[12:]
				h := sha3.NewLegacyKeccak256()
				h.Write(initCode)
				codeHash := h.Sum(nil)

				h2 := sha3.NewLegacyKeccak256()
				h2.Write([]byte{0xff})
				h2.Write(ctx.Call.Address[:])
				var saltBytes [32]byte
				if salt != nil {
					safeFillBytes(salt, saltBytes[:])
				}
				h2.Write(saltBytes[:])
				h2.Write(codeHash)
				copy(newAddr[:], h2.Sum(nil)[12:])
			}

			// Increment caller nonce
			interp.state.SetNonce(ctx.Call.Address, callerNonce+1)

			// Snapshot for rollback
			snapID := interp.state.Snapshot()

			// Create new account
			interp.state.CreateAccount(newAddr)

			// Transfer value
			if val.Sign() > 0 {
				senderBal := interp.state.GetBalance(ctx.Call.Address)
				if senderBal.Cmp(val) < 0 {
					interp.state.RevertToSnapshot(snapID)
					err = ctx.Stack.Push(big.NewInt(0))
					break
				}
				interp.state.SetBalance(ctx.Call.Address, new(big.Int).Sub(senderBal, val))
				interp.state.SetBalance(newAddr, new(big.Int).Add(interp.state.GetBalance(newAddr), val))
			}

			// Execute init code as a sub-call
			subGas := ctx.GasRemaining() - ctx.GasRemaining()/64 // EIP-150: retain 1/64
			subCall := &CallContext{
				Caller:  ctx.Call.Address,
				Address: newAddr,
				Value:   val,
				Code:    initCode,
				Gas:     subGas,
				Depth:   ctx.Call.Depth + 1,
			}
			subResult := interp.Execute(ctx.Block, ctx.Tx, subCall)

			if subResult.Success && len(subResult.ReturnData) > 0 {
				// Code deposit: check EIP-170 max code size
				if uint64(len(subResult.ReturnData)) > MaxCodeSize {
					interp.state.RevertToSnapshot(snapID)
					err = ctx.Stack.Push(big.NewInt(0))
				} else {
					// Charge code deposit gas
					depositGas := GasCodeDeposit * uint64(len(subResult.ReturnData))
					if !ctx.UseGas(depositGas + subResult.GasUsed) {
						interp.state.RevertToSnapshot(snapID)
						err = ctx.Stack.Push(big.NewInt(0))
					} else {
						interp.state.SetCode(newAddr, subResult.ReturnData)
						err = ctx.Stack.Push(new(big.Int).SetBytes(newAddr[:]))
					}
				}
			} else {
				ctx.UseGas(subResult.GasUsed)
				if !subResult.Success {
					interp.state.RevertToSnapshot(snapID)
				}
				err = ctx.Stack.Push(big.NewInt(0))
			}

		case op == CALL || op == CALLCODE || op == DELEGATECALL || op == STATICCALL:
			gasInt := mustPop1(ctx)
			addrInt := mustPop1(ctx)
			var callValue *big.Int
			if op == CALL || op == CALLCODE {
				callValue = mustPop1(ctx)
			} else {
				callValue = big.NewInt(0)
			}
			argsOff, argsLen := mustPop2(ctx)
			retOff, retLen := mustPop2(ctx)

			var toAddr [20]byte
			safeAddrBytes(addrInt, &toAddr)

			aOff, aLen := argsOff.Uint64(), argsLen.Uint64()
			rOff, rLen := retOff.Uint64(), retLen.Uint64()

			// Memory expansion for args + return
			memCost := ctx.Memory.Resize(aOff + aLen)
			memCost += ctx.Memory.Resize(rOff + rLen)
			if !ctx.UseGas(memCost) {
				return fmt.Errorf("out of gas: CALL memory")
			}

			// Check for precompile
			toAddrInt := new(big.Int).SetBytes(toAddr[:])
			if toAddrInt.Uint64() > 0 && toAddrInt.Uint64() <= 9 && IsPrecompile(toAddrInt.Uint64()) {
				callArgs := ctx.Memory.Get(aOff, aLen)
				subGas := gasInt.Uint64()
				if subGas > ctx.GasRemaining() {
					subGas = ctx.GasRemaining()
				}
				output, gasUsed, preErr := ExecutePrecompile(toAddrInt.Uint64(), callArgs, subGas)
				ctx.UseGas(gasUsed)
				if preErr != nil {
					err = ctx.Stack.Push(big.NewInt(0))
				} else {
					// Copy return data
					ctx.ReturnData = output
					copyLen := rLen
					if uint64(len(output)) < copyLen {
						copyLen = uint64(len(output))
					}
					if copyLen > 0 {
						ctx.Memory.Set(rOff, output[:copyLen])
					}
					err = ctx.Stack.Push(big.NewInt(1))
				}
				break
			}

			if interp.state == nil {
				err = ctx.Stack.Push(big.NewInt(0))
				break
			}

			// EIP-2929: warm/cold address access
			if !ctx.AccessList.IsAddressWarm(toAddr) {
				ctx.AccessList.MarkAddressWarm(toAddr)
				if !ctx.UseGas(GasCallCold - GasCallWarm) {
					return fmt.Errorf("out of gas: CALL cold address")
				}
			}

			// Calculate sub-call gas (EIP-150: max 63/64 of remaining)
			subGas := gasInt.Uint64()
			maxGas := ctx.GasRemaining() - ctx.GasRemaining()/64
			if subGas > maxGas {
				subGas = maxGas
			}

			// Value transfer gas
			if callValue.Sign() > 0 {
				if !ctx.UseGas(GasCallValue) {
					return fmt.Errorf("out of gas: CALL value transfer")
				}
				if !interp.state.AccountExists(toAddr) {
					if !ctx.UseGas(GasCallNewAcct) {
						return fmt.Errorf("out of gas: CALL new account")
					}
				}
				subGas += GasCallStipend // stipend for non-zero value calls
			}

			callArgs := ctx.Memory.Get(aOff, aLen)

			// Snapshot for rollback
			snapID := interp.state.Snapshot()

			// Value transfer
			if callValue.Sign() > 0 && (op == CALL || op == CALLCODE) {
				senderBal := interp.state.GetBalance(ctx.Call.Address)
				if senderBal.Cmp(callValue) < 0 {
					interp.state.RevertToSnapshot(snapID)
					err = ctx.Stack.Push(big.NewInt(0))
					break
				}
				interp.state.SetBalance(ctx.Call.Address, new(big.Int).Sub(senderBal, callValue))
				interp.state.SetBalance(toAddr, new(big.Int).Add(interp.state.GetBalance(toAddr), callValue))
			}

			// Build sub-call context
			targetCode := interp.state.GetCode(toAddr)
			subCall := &CallContext{
				Input: callArgs,
				Gas:   subGas,
				Value: callValue,
				Depth: ctx.Call.Depth + 1,
			}
			switch op {
			case CALL:
				subCall.Caller = ctx.Call.Address
				subCall.Address = toAddr
				subCall.Code = targetCode
				subCall.IsStatic = ctx.Call.IsStatic
			case CALLCODE:
				subCall.Caller = ctx.Call.Address
				subCall.Address = ctx.Call.Address // code runs in caller's context
				subCall.Code = targetCode
			case DELEGATECALL:
				subCall.Caller = ctx.Call.Caller // preserve original caller
				subCall.Address = ctx.Call.Address // code runs in caller's context
				subCall.Code = targetCode
				subCall.Value = ctx.Call.Value // preserve original value
			case STATICCALL:
				subCall.Caller = ctx.Call.Address
				subCall.Address = toAddr
				subCall.Code = targetCode
				subCall.IsStatic = true
			}

			var subResult *ExecutionResult
			if len(subCall.Code) > 0 {
				subResult = interp.Execute(ctx.Block, ctx.Tx, subCall)
			} else {
				// Empty code = success with no return data
				subResult = &ExecutionResult{Success: true}
			}

			ctx.UseGas(subResult.GasUsed)
			ctx.ReturnData = subResult.ReturnData

			if subResult.Success {
				copyLen := rLen
				if uint64(len(subResult.ReturnData)) < copyLen {
					copyLen = uint64(len(subResult.ReturnData))
				}
				if copyLen > 0 {
					ctx.Memory.Set(rOff, subResult.ReturnData[:copyLen])
				}
				err = ctx.Stack.Push(big.NewInt(1))
			} else {
				interp.state.RevertToSnapshot(snapID)
				err = ctx.Stack.Push(big.NewInt(0))
			}

		case op == SELFDESTRUCT:
			if ctx.Call.IsStatic {
				return fmt.Errorf("SELFDESTRUCT in static context")
			}
			if !ctx.UseGas(GasSelfDestruct) {
				return fmt.Errorf("out of gas: SELFDESTRUCT")
			}
			beneficiaryInt := mustPop1(ctx)
			var beneficiary [20]byte
			safeAddrBytes(beneficiaryInt, &beneficiary)

			if interp.state != nil {
				// EIP-2929: cold address surcharge
				if !ctx.AccessList.IsAddressWarm(beneficiary) {
					ctx.AccessList.MarkAddressWarm(beneficiary)
					if !ctx.UseGas(GasCallCold) {
						return fmt.Errorf("out of gas: SELFDESTRUCT cold address")
					}
				}

				// Transfer entire balance to beneficiary
				balance := interp.state.GetBalance(ctx.Call.Address)
				if balance.Sign() > 0 {
					// New account creation gas if beneficiary doesn't exist
					if !interp.state.AccountExists(beneficiary) && balance.Sign() > 0 {
						if !ctx.UseGas(GasCallNewAcct) {
							return fmt.Errorf("out of gas: SELFDESTRUCT new account")
						}
					}
					beneficiaryBal := interp.state.GetBalance(beneficiary)
					interp.state.SetBalance(beneficiary, new(big.Int).Add(beneficiaryBal, balance))
					interp.state.SetBalance(ctx.Call.Address, big.NewInt(0))
				}
			}
			ctx.Stopped = true

		default:
			return fmt.Errorf("unknown opcode 0x%02x at PC=%d", byte(op), ctx.PC)
		}

		if err != nil {
			return err
		}

		ctx.PC++
	}

	return nil
}

// opCopy implements CALLDATACOPY / CODECOPY pattern.
func (interp *Interpreter) opCopy(ctx *ExecutionContext, source []byte) error {
	destOff, srcOff, size := mustPop3(ctx)
	sz := size.Uint64()
	copyCost := CopyGasCost(sz)
	memCost := ctx.Memory.Resize(destOff.Uint64() + sz)
	if !ctx.UseGas(copyCost + memCost) {
		return fmt.Errorf("out of gas: COPY")
	}
	data := padRight(sliceBytes(source, srcOff.Uint64(), sz), int(sz))
	ctx.Memory.Set(destOff.Uint64(), data)
	return nil
}

// ─── Helpers ──────────────────────────────────────────────────────────

// errStackUnderflow is the sentinel error for EVM stack underflow.
// Per EVM spec, stack underflow is an exceptional halt that consumes all gas.
var errStackUnderflow = fmt.Errorf("stack underflow")

func mustPop1(ctx *ExecutionContext) *big.Int {
	val, err := ctx.Stack.Pop()
	if err != nil || val == nil {
		// EVM spec: stack underflow = exceptional halt (consume all gas)
		ctx.Stopped = true
		ctx.GasUsed = ctx.Call.Gas // consume all remaining gas
		log.Printf("EVM exceptional halt: stack underflow at PC=%d", ctx.PC)
		return big.NewInt(0)
	}
	return val
}

func mustPop2(ctx *ExecutionContext) (*big.Int, *big.Int) {
	a := mustPop1(ctx)
	b := mustPop1(ctx)
	return a, b
}

func mustPop3(ctx *ExecutionContext) (*big.Int, *big.Int, *big.Int) {
	a := mustPop1(ctx)
	b := mustPop1(ctx)
	c := mustPop1(ctx)
	return a, b, c
}

// safeAddrBytes extracts at most 20 address bytes from a big.Int,
// truncating values larger than 2^160 instead of panicking.
func safeAddrBytes(v *big.Int, addr *[20]byte) {
	b := v.Bytes()
	if len(b) > 20 {
		b = b[len(b)-20:] // take rightmost 20 bytes
	}
	copy(addr[20-len(b):], b)
}

// safeFillBytes copies big.Int bytes into dst, truncating if the
// value is larger than the destination to prevent FillBytes panics.
func safeFillBytes(v *big.Int, dst []byte) {
	b := v.Bytes()
	if len(b) > len(dst) {
		b = b[len(b)-len(dst):]
	}
	// zero-fill prefix then copy
	for i := range dst {
		dst[i] = 0
	}
	copy(dst[len(dst)-len(b):], b)
}

func pushBool(ctx *ExecutionContext, val bool) error {
	if val {
		return ctx.Stack.Push(big.NewInt(1))
	}
	return ctx.Stack.Push(big.NewInt(0))
}

// sliceBytes returns source[offset:offset+size], handling out-of-bounds gracefully.
func sliceBytes(source []byte, offset, size uint64) []byte {
	if size == 0 {
		return nil
	}
	if offset >= uint64(len(source)) {
		return make([]byte, 0)
	}
	end := offset + size
	if end > uint64(len(source)) {
		end = uint64(len(source))
	}
	return source[offset:end]
}

// padRight pads data with zero bytes to the given length.
func padRight(data []byte, length int) []byte {
	if len(data) >= length {
		return data[:length]
	}
	padded := make([]byte, length)
	copy(padded, data)
	return padded
}
