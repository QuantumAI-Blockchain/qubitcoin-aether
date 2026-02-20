// Package state implements the QVM state management layer.
//
// Provides:
//   - Merkle Patricia Trie for account/storage state
//   - Quantum state persistence (density matrices)
//   - State root computation for block headers
//   - State diff computation for rollbacks
//   - Snapshot and restore for debugging
//
// The state root is computed from:
//   - Account trie (balances, nonces, code hashes)
//   - Storage trie (contract storage slots)
//   - Quantum state trie (quantum state density matrices)
//
// Block header includes:
//   - state_root (32 bytes) — Merkle root of account+storage state
//   - quantum_state_root (32 bytes) — Merkle root of quantum states
//   - compliance_root (32 bytes) — Merkle root of compliance proofs
package state

// StateRoot represents a 32-byte Merkle root hash.
type StateRoot [32]byte

// Account represents a QVM account.
type Account struct {
	Address  [20]byte
	Balance  [32]byte // uint256 big-endian
	Nonce    uint64
	CodeHash [32]byte
	Root     StateRoot // storage trie root
}

// StorageSlot represents a single storage slot in a contract.
type StorageSlot struct {
	Key   [32]byte
	Value [32]byte
}

// StateSnapshot captures the complete state at a point in time.
type StateSnapshot struct {
	BlockNumber      uint64
	StateRoot        StateRoot
	QuantumStateRoot StateRoot
	ComplianceRoot   StateRoot
	Accounts         map[[20]byte]*Account
}
