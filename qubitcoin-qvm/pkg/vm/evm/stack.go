// Package evm implements the EVM-compatible bytecode interpreter.
//
// stack.go provides the 1024-item bounded stack used by the EVM.
// Values are 256-bit unsigned integers stored as [4]uint64 (little-endian limbs).
// For simplicity and compatibility with go-ethereum, we use math/big internally
// but store values on a pool-backed slice for allocation efficiency.
package evm

import (
	"fmt"
	"math/big"
)

// MaxStackDepth is the EVM stack limit.
const MaxStackDepth = 1024

// uint256 constants.
var (
	big0       = new(big.Int)
	big1       = new(big.Int).SetUint64(1)
	big32      = new(big.Int).SetUint64(32)
	big256     = new(big.Int).SetUint64(256)
	maxUint256 = new(big.Int).Sub(new(big.Int).Lsh(big1, 256), big1)
	uint256Mod = new(big.Int).Lsh(big1, 256)
)

// Stack is a 1024-item bounded stack of 256-bit integers.
type Stack struct {
	data []*big.Int
}

// NewStack creates a new empty stack.
func NewStack() *Stack {
	return &Stack{
		data: make([]*big.Int, 0, 16),
	}
}

// Len returns the number of items on the stack.
func (s *Stack) Len() int {
	return len(s.data)
}

// Push pushes a 256-bit value onto the stack.
// Returns an error if the stack would exceed MaxStackDepth.
func (s *Stack) Push(val *big.Int) error {
	if len(s.data) >= MaxStackDepth {
		return fmt.Errorf("stack overflow: depth %d exceeds max %d", len(s.data)+1, MaxStackDepth)
	}
	// Mask to 256 bits.
	v := new(big.Int).And(val, maxUint256)
	s.data = append(s.data, v)
	return nil
}

// PushUint64 pushes a uint64 value onto the stack.
func (s *Stack) PushUint64(val uint64) error {
	return s.Push(new(big.Int).SetUint64(val))
}

// Pop removes and returns the top value from the stack.
func (s *Stack) Pop() (*big.Int, error) {
	if len(s.data) == 0 {
		return nil, fmt.Errorf("stack underflow")
	}
	val := s.data[len(s.data)-1]
	s.data = s.data[:len(s.data)-1]
	return val, nil
}

// Peek returns the value at the given depth without removing it.
// Depth 0 is the top of the stack.
func (s *Stack) Peek(depth int) (*big.Int, error) {
	if depth >= len(s.data) {
		return nil, fmt.Errorf("stack underflow: peek depth %d, size %d", depth, len(s.data))
	}
	return s.data[len(s.data)-1-depth], nil
}

// Swap swaps the top element with the element at the given depth.
// Depth 1 means swap top with second element (SWAP1).
func (s *Stack) Swap(depth int) error {
	if depth >= len(s.data) || depth < 1 {
		return fmt.Errorf("stack underflow: swap depth %d, size %d", depth, len(s.data))
	}
	top := len(s.data) - 1
	s.data[top], s.data[top-depth] = s.data[top-depth], s.data[top]
	return nil
}

// Dup duplicates the element at the given depth and pushes it on top.
// Depth 1 means duplicate the top element (DUP1).
func (s *Stack) Dup(depth int) error {
	if depth > len(s.data) || depth < 1 {
		return fmt.Errorf("stack underflow: dup depth %d, size %d", depth, len(s.data))
	}
	val := s.data[len(s.data)-depth]
	return s.Push(new(big.Int).Set(val))
}

// Back returns the top element without removing it.
func (s *Stack) Back() (*big.Int, error) {
	return s.Peek(0)
}

// Reset clears the stack.
func (s *Stack) Reset() {
	s.data = s.data[:0]
}

// ToSignedBig interprets a 256-bit unsigned value as a signed 256-bit value
// (two's complement).
func ToSignedBig(val *big.Int) *big.Int {
	// If bit 255 is set, the value is negative.
	if val.Bit(255) == 1 {
		// Compute -(2^256 - val)
		result := new(big.Int).Sub(uint256Mod, val)
		return result.Neg(result)
	}
	return new(big.Int).Set(val)
}

// ToUnsignedBig converts a signed big.Int back to unsigned 256-bit representation.
func ToUnsignedBig(val *big.Int) *big.Int {
	if val.Sign() < 0 {
		return new(big.Int).Add(uint256Mod, val)
	}
	return new(big.Int).And(val, maxUint256)
}

// U256 masks val to 256 bits (val mod 2^256).
func U256(val *big.Int) *big.Int {
	return new(big.Int).And(val, maxUint256)
}
