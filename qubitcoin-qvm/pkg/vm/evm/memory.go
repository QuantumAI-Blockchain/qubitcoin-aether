package evm

import (
	"fmt"
	"math/big"
)

// MaxMemorySize is the maximum allowed memory size (32 MB).
// This prevents denial-of-service via unbounded memory allocation.
const MaxMemorySize = 32 * 1024 * 1024

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

// ErrMaxMemoryExceeded is returned when a memory resize would exceed MaxMemorySize.
var ErrMaxMemoryExceeded = fmt.Errorf("memory expansion exceeds maximum (%d bytes)", MaxMemorySize)

// Resize grows memory to at least size bytes (word-aligned to 32 bytes).
// Returns the gas cost of expansion and an error if the requested size exceeds MaxMemorySize.
func (m *Memory) Resize(size uint64) (uint64, error) {
	if size == 0 || uint64(len(m.store)) >= size {
		return 0, nil
	}
	if size > MaxMemorySize {
		return 0, fmt.Errorf("memory: Resize exceeds max (%d > %d)", size, MaxMemorySize)
	}
	oldWords := toWordSize(uint64(len(m.store)))
	newWords := toWordSize(size)
	if newWords <= oldWords {
		return 0, nil
	}

	oldCost := memoryCost(oldWords)
	newCost := memoryCost(newWords)
	gasCost := newCost - oldCost

	// Extend to word boundary
	newSize := newWords * 32
	if newSize > MaxMemorySize {
		return 0, fmt.Errorf("memory: Resize exceeds max (%d > %d)", newSize, MaxMemorySize)
	}
	m.store = append(m.store, make([]byte, newSize-uint64(len(m.store)))...)

	return gasCost, nil
}

// Set writes data to memory at the given offset.
// Returns an error if the write is out of bounds.
func (m *Memory) Set(offset uint64, data []byte) error {
	if len(data) == 0 {
		return nil
	}
	end := offset + uint64(len(data))
	if end > uint64(len(m.store)) || end < offset {
		return fmt.Errorf("memory: Set out of bounds: offset=%d len=%d store=%d", offset, len(data), len(m.store))
	}
	copy(m.store[offset:end], data)
	return nil
}

// Set32 writes a 32-byte big-endian value to memory at the given offset.
// Returns an error if the write is out of bounds.
func (m *Memory) Set32(offset uint64, val *big.Int) error {
	end := offset + 32
	if end > uint64(len(m.store)) || end < offset {
		return fmt.Errorf("memory: Set32 out of bounds: offset=%d store=%d", offset, len(m.store))
	}
	var buf [32]byte
	val.FillBytes(buf[:])
	copy(m.store[offset:end], buf[:])
	return nil
}

// SetByte writes a single byte to memory.
// Returns an error if the offset is out of bounds.
func (m *Memory) SetByte(offset uint64, val byte) error {
	if offset >= uint64(len(m.store)) {
		return fmt.Errorf("memory: SetByte out of bounds: offset=%d store=%d", offset, len(m.store))
	}
	m.store[offset] = val
	return nil
}

// Get returns a copy of data from memory at the given offset and size.
// Returns an error if the read is out of bounds.
func (m *Memory) Get(offset, size uint64) ([]byte, error) {
	if size == 0 {
		return nil, nil
	}
	end := offset + size
	if end > uint64(len(m.store)) || end < offset {
		return nil, fmt.Errorf("memory: Get out of bounds: offset=%d size=%d store=%d", offset, size, len(m.store))
	}
	out := make([]byte, size)
	copy(out, m.store[offset:end])
	return out, nil
}

// GetPtr returns a slice reference (not a copy) for read-only use.
// Returns an error if the access is out of bounds.
func (m *Memory) GetPtr(offset, size uint64) ([]byte, error) {
	if size == 0 {
		return nil, nil
	}
	end := offset + size
	if end > uint64(len(m.store)) || end < offset {
		return nil, fmt.Errorf("memory: GetPtr out of bounds: offset=%d size=%d store=%d", offset, size, len(m.store))
	}
	return m.store[offset:end], nil
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
	if end > MaxMemorySize {
		return 0, ErrMaxMemoryExceeded
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
