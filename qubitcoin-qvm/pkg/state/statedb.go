// Package state implements the QVM state management layer.
//
// statedb.go provides the in-memory StateDB that implements the
// evm.StateAccessor interface. It manages account balances, nonces,
// contract code, and storage slots with snapshot/revert support for
// transaction atomicity.
package state

import (
	"crypto/sha256"
	"math/big"
	"sync"
)

// StateDB is the in-memory state database implementing evm.StateAccessor.
// It provides account, storage, and code management with snapshot/revert
// capability for transactional execution.
type StateDB struct {
	mu sync.RWMutex

	// Account state
	accounts map[[20]byte]*Account
	// Contract code (keyed by code hash)
	codes map[[32]byte][]byte
	// Contract storage (keyed by address → key → value)
	storage map[[20]byte]map[[32]byte][32]byte

	// Block hashes for BLOCKHASH opcode (last 256 blocks)
	blockHashes map[uint64][32]byte

	// Snapshot stack for revert support
	snapshots []snapshot

	// Journal of changes for revert
	journal []journalEntry
}

// snapshot records the state at a point in time.
type snapshot struct {
	journalLen int
}

// journalEntry records a single state change for revert.
type journalEntry struct {
	kind    journalKind
	addr    [20]byte
	key     [32]byte
	prevVal [32]byte
	prevAcc *Account
}

type journalKind uint8

const (
	journalStorage journalKind = iota
	journalBalance
	journalNonce
	journalCode
	journalCreate
)

// NewStateDB creates a new empty state database.
func NewStateDB() *StateDB {
	return &StateDB{
		accounts:    make(map[[20]byte]*Account),
		codes:       make(map[[32]byte][]byte),
		storage:     make(map[[20]byte]map[[32]byte][32]byte),
		blockHashes: make(map[uint64][32]byte),
	}
}

// ─── evm.StateAccessor interface ──────────────────────────────────────

// GetStorage returns the value at a storage slot for an address.
func (s *StateDB) GetStorage(addr [20]byte, key [32]byte) [32]byte {
	s.mu.RLock()
	defer s.mu.RUnlock()

	if slots, ok := s.storage[addr]; ok {
		if val, ok := slots[key]; ok {
			return val
		}
	}
	return [32]byte{}
}

// SetStorage sets a storage slot value for an address.
func (s *StateDB) SetStorage(addr [20]byte, key [32]byte, val [32]byte) {
	s.mu.Lock()
	defer s.mu.Unlock()

	// Record for journal (revert support)
	prev := [32]byte{}
	if slots, ok := s.storage[addr]; ok {
		prev = slots[key]
	}
	s.journal = append(s.journal, journalEntry{
		kind:    journalStorage,
		addr:    addr,
		key:     key,
		prevVal: prev,
	})

	if _, ok := s.storage[addr]; !ok {
		s.storage[addr] = make(map[[32]byte][32]byte)
	}
	s.storage[addr][key] = val
}

// GetBalance returns the balance of an address.
func (s *StateDB) GetBalance(addr [20]byte) *big.Int {
	s.mu.RLock()
	defer s.mu.RUnlock()

	acc := s.accounts[addr]
	if acc == nil {
		return big.NewInt(0)
	}
	return new(big.Int).SetBytes(acc.Balance[:])
}

// SetBalance sets the balance of an address.
func (s *StateDB) SetBalance(addr [20]byte, balance *big.Int) {
	s.mu.Lock()
	defer s.mu.Unlock()

	acc := s.getOrCreateAccount(addr)

	// Journal the previous state
	prevAcc := *acc
	s.journal = append(s.journal, journalEntry{
		kind:    journalBalance,
		addr:    addr,
		prevAcc: &prevAcc,
	})

	var bal [32]byte
	b := balance.Bytes()
	if len(b) > 32 {
		b = b[:32]
	}
	copy(bal[32-len(b):], b)
	acc.Balance = bal
}

// GetNonce returns the nonce for an address.
func (s *StateDB) GetNonce(addr [20]byte) uint64 {
	s.mu.RLock()
	defer s.mu.RUnlock()

	acc := s.accounts[addr]
	if acc == nil {
		return 0
	}
	return acc.Nonce
}

// SetNonce sets the nonce for an address.
func (s *StateDB) SetNonce(addr [20]byte, nonce uint64) {
	s.mu.Lock()
	defer s.mu.Unlock()

	acc := s.getOrCreateAccount(addr)
	prevAcc := *acc
	s.journal = append(s.journal, journalEntry{
		kind:    journalNonce,
		addr:    addr,
		prevAcc: &prevAcc,
	})
	acc.Nonce = nonce
}

// GetCodeHash returns the code hash for an address.
func (s *StateDB) GetCodeHash(addr [20]byte) [32]byte {
	s.mu.RLock()
	defer s.mu.RUnlock()

	acc := s.accounts[addr]
	if acc == nil {
		return [32]byte{}
	}
	return acc.CodeHash
}

// GetCode returns the bytecode for an address.
func (s *StateDB) GetCode(addr [20]byte) []byte {
	s.mu.RLock()
	defer s.mu.RUnlock()

	acc := s.accounts[addr]
	if acc == nil {
		return nil
	}
	return s.codes[acc.CodeHash]
}

// GetCodeSize returns the size of the bytecode for an address.
func (s *StateDB) GetCodeSize(addr [20]byte) uint64 {
	code := s.GetCode(addr)
	return uint64(len(code))
}

// SetCode stores bytecode for an address.
func (s *StateDB) SetCode(addr [20]byte, code []byte) {
	s.mu.Lock()
	defer s.mu.Unlock()

	acc := s.getOrCreateAccount(addr)
	prevAcc := *acc
	s.journal = append(s.journal, journalEntry{
		kind:    journalCode,
		addr:    addr,
		prevAcc: &prevAcc,
	})

	hash := sha256.Sum256(code)
	acc.CodeHash = hash
	s.codes[hash] = make([]byte, len(code))
	copy(s.codes[hash], code)
}

// GetBlockHash returns the hash of a previous block (BLOCKHASH opcode).
func (s *StateDB) GetBlockHash(num uint64) [32]byte {
	s.mu.RLock()
	defer s.mu.RUnlock()
	return s.blockHashes[num]
}

// SetBlockHash stores a block hash for BLOCKHASH lookups.
func (s *StateDB) SetBlockHash(num uint64, hash [32]byte) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.blockHashes[num] = hash
}

// ─── Account management ───────────────────────────────────────────────

// AccountExists returns true if an account exists.
func (s *StateDB) AccountExists(addr [20]byte) bool {
	s.mu.RLock()
	defer s.mu.RUnlock()
	_, ok := s.accounts[addr]
	return ok
}

// CreateAccount creates a new account (used by CREATE/CREATE2).
func (s *StateDB) CreateAccount(addr [20]byte) {
	s.mu.Lock()
	defer s.mu.Unlock()

	s.journal = append(s.journal, journalEntry{
		kind: journalCreate,
		addr: addr,
	})
	s.accounts[addr] = &Account{Address: addr}
}

// getOrCreateAccount returns the account, creating it if it doesn't exist.
// Must be called with s.mu held.
func (s *StateDB) getOrCreateAccount(addr [20]byte) *Account {
	acc, ok := s.accounts[addr]
	if !ok {
		acc = &Account{Address: addr}
		s.accounts[addr] = acc
	}
	return acc
}

// ─── Snapshot / Revert ────────────────────────────────────────────────

// Snapshot takes a snapshot of the current state. Returns the snapshot ID.
func (s *StateDB) Snapshot() int {
	s.mu.Lock()
	defer s.mu.Unlock()

	id := len(s.snapshots)
	s.snapshots = append(s.snapshots, snapshot{
		journalLen: len(s.journal),
	})
	return id
}

// RevertToSnapshot reverts state to a previous snapshot.
func (s *StateDB) RevertToSnapshot(id int) {
	s.mu.Lock()
	defer s.mu.Unlock()

	if id >= len(s.snapshots) {
		return
	}

	snap := s.snapshots[id]

	// Replay journal in reverse to undo changes
	for i := len(s.journal) - 1; i >= snap.journalLen; i-- {
		entry := s.journal[i]
		switch entry.kind {
		case journalStorage:
			if slots, ok := s.storage[entry.addr]; ok {
				if entry.prevVal == ([32]byte{}) {
					delete(slots, entry.key)
				} else {
					slots[entry.key] = entry.prevVal
				}
			}
		case journalBalance, journalNonce, journalCode:
			if entry.prevAcc != nil {
				prev := *entry.prevAcc
				s.accounts[entry.addr] = &prev
			}
		case journalCreate:
			delete(s.accounts, entry.addr)
			delete(s.storage, entry.addr)
		}
	}

	// Trim journal and snapshots
	s.journal = s.journal[:snap.journalLen]
	s.snapshots = s.snapshots[:id]
}

// Commit finalizes state changes (clears journal and snapshots).
func (s *StateDB) Commit() {
	s.mu.Lock()
	defer s.mu.Unlock()

	s.journal = s.journal[:0]
	s.snapshots = s.snapshots[:0]
}

// ─── State root computation ───────────────────────────────────────────

// ComputeStateRoot computes a Merkle root over all accounts and storage.
// This is a simplified hash — production uses a Merkle Patricia Trie.
func (s *StateDB) ComputeStateRoot() StateRoot {
	s.mu.RLock()
	defer s.mu.RUnlock()

	h := sha256.New()
	for addr, acc := range s.accounts {
		h.Write(addr[:])
		h.Write(acc.Balance[:])
		nonceBytes := big.NewInt(int64(acc.Nonce)).Bytes()
		h.Write(nonceBytes)
		h.Write(acc.CodeHash[:])
		h.Write(acc.Root[:])
	}

	var root StateRoot
	copy(root[:], h.Sum(nil))
	return root
}

// AccountCount returns the number of accounts in the state.
func (s *StateDB) AccountCount() int {
	s.mu.RLock()
	defer s.mu.RUnlock()
	return len(s.accounts)
}
