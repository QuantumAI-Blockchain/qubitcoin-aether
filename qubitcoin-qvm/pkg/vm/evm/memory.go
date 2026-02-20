package evm

import (
	"fmt"
	"math/big"
)

// Memory implements the EVM's linear byte-addressable memory.
// Memory is word-aligned (32 bytes) and grows dynamically.
// Expansion cost follows the EVM specification:
//
//	cost = 3 * words + words^2 / 512
type Memory struct {
	store []byte
}

// NewMemory creates a new empty memory instance.
func NewMemory() *Memory {
	return &Memory{
		store: make([]byte, 0, 4096),
	}
}

// Len returns the current size of memory in bytes.
func (m *Memory) Len() int {
	return len(m.store)
}

// Resize grows memory to at least size bytes (word-aligned to 32 bytes).
// Returns the gas cost of expansion (0 if no expansion needed).
func (m *Memory) Resize(size uint64) uint64 {
	if size == 0 || uint64(len(m.store)) >= size {
		return 0
	}
	oldWords := toWordSize(uint64(len(m.store)))
	newWords := toWordSize(size)
	if newWords <= oldWords {
		return 0
	}

	oldCost := memoryCost(oldWords)
	newCost := memoryCost(newWords)
	gasCost := newCost - oldCost

	// Extend to word boundary
	newSize := newWords * 32
	m.store = append(m.store, make([]byte, newSize-uint64(len(m.store)))...)

	return gasCost
}

// Set writes data to memory at the given offset.
// Caller must ensure memory has been resized before calling Set.
func (m *Memory) Set(offset uint64, data []byte) {
	if len(data) == 0 {
		return
	}
	copy(m.store[offset:offset+uint64(len(data))], data)
}

// Set32 writes a 32-byte big-endian value to memory at the given offset.
func (m *Memory) Set32(offset uint64, val *big.Int) {
	var buf [32]byte
	val.FillBytes(buf[:])
	copy(m.store[offset:offset+32], buf[:])
}

// SetByte writes a single byte to memory.
func (m *Memory) SetByte(offset uint64, val byte) {
	m.store[offset] = val
}

// Get returns a copy of data from memory at the given offset and size.
func (m *Memory) Get(offset, size uint64) []byte {
	if size == 0 {
		return nil
	}
	out := make([]byte, size)
	copy(out, m.store[offset:offset+size])
	return out
}

// GetPtr returns a slice reference (not a copy) for read-only use.
func (m *Memory) GetPtr(offset, size uint64) []byte {
	if size == 0 {
		return nil
	}
	return m.store[offset : offset+size]
}

// Reset clears memory.
func (m *Memory) Reset() {
	m.store = m.store[:0]
}

// Data returns the full memory content as a byte slice.
func (m *Memory) Data() []byte {
	return m.store
}

// CalcExpansionCost computes the gas cost to expand memory to cover [offset, offset+size).
// Returns 0 if no expansion is needed or size is 0.
func (m *Memory) CalcExpansionCost(offset, size uint64) (uint64, error) {
	if size == 0 {
		return 0, nil
	}
	end, overflow := safeAdd(offset, size)
	if overflow {
		return 0, fmt.Errorf("memory offset overflow: %d + %d", offset, size)
	}
	if uint64(len(m.store)) >= end {
		return 0, nil
	}
	oldWords := toWordSize(uint64(len(m.store)))
	newWords := toWordSize(end)
	if newWords <= oldWords {
		return 0, nil
	}
	return memoryCost(newWords) - memoryCost(oldWords), nil
}

// toWordSize rounds up a byte size to the number of 32-byte words.
func toWordSize(byteSize uint64) uint64 {
	return (byteSize + 31) / 32
}

// memoryCost computes the gas cost for a given number of 32-byte words:
//
//	cost = 3 * words + words^2 / 512
func memoryCost(words uint64) uint64 {
	return 3*words + (words*words)/512
}

// safeAdd adds two uint64 values and returns true if overflow occurred.
func safeAdd(a, b uint64) (uint64, bool) {
	sum := a + b
	return sum, sum < a
}
