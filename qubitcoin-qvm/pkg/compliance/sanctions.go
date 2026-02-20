package compliance

import (
	"sync"
)

// SanctionsChecker maintains a sanctions list and checks addresses.
// Supports multiple sanctions sources (OFAC, EU, UN) with add/remove.
// The QCOMPLIANCE opcode calls this before allowing transactions.
type SanctionsChecker struct {
	mu      sync.RWMutex
	entries map[[20]byte]*SanctionsEntry
}

// NewSanctionsChecker creates a new sanctions checker.
func NewSanctionsChecker() *SanctionsChecker {
	return &SanctionsChecker{
		entries: make(map[[20]byte]*SanctionsEntry),
	}
}

// AddEntry adds an address to the sanctions list.
func (sc *SanctionsChecker) AddEntry(addr [20]byte, source string, blockNum uint64) {
	sc.mu.Lock()
	defer sc.mu.Unlock()

	sc.entries[addr] = &SanctionsEntry{
		Address:  addr,
		ListedAt: blockNum,
		Source:   source,
		Active:   true,
	}
}

// RemoveEntry deactivates a sanctions entry (does not delete for audit trail).
func (sc *SanctionsChecker) RemoveEntry(addr [20]byte) {
	sc.mu.Lock()
	defer sc.mu.Unlock()

	if entry, ok := sc.entries[addr]; ok {
		entry.Active = false
	}
}

// IsSanctioned checks if an address is on the active sanctions list.
func (sc *SanctionsChecker) IsSanctioned(addr [20]byte) bool {
	sc.mu.RLock()
	defer sc.mu.RUnlock()

	entry, ok := sc.entries[addr]
	return ok && entry.Active
}

// GetEntry returns the sanctions entry for an address, or nil if not listed.
func (sc *SanctionsChecker) GetEntry(addr [20]byte) *SanctionsEntry {
	sc.mu.RLock()
	defer sc.mu.RUnlock()

	return sc.entries[addr]
}

// CheckTransaction verifies that neither sender nor receiver is sanctioned.
// Returns (allowed, reason).
func (sc *SanctionsChecker) CheckTransaction(sender, receiver [20]byte) (bool, string) {
	sc.mu.RLock()
	defer sc.mu.RUnlock()

	if entry, ok := sc.entries[sender]; ok && entry.Active {
		return false, "sender is sanctioned (" + entry.Source + ")"
	}
	if entry, ok := sc.entries[receiver]; ok && entry.Active {
		return false, "receiver is sanctioned (" + entry.Source + ")"
	}

	return true, ""
}

// ActiveCount returns the number of active sanctions entries.
func (sc *SanctionsChecker) ActiveCount() int {
	sc.mu.RLock()
	defer sc.mu.RUnlock()

	count := 0
	for _, e := range sc.entries {
		if e.Active {
			count++
		}
	}
	return count
}

// AllEntries returns all sanctions entries (active and inactive).
func (sc *SanctionsChecker) AllEntries() []*SanctionsEntry {
	sc.mu.RLock()
	defer sc.mu.RUnlock()

	result := make([]*SanctionsEntry, 0, len(sc.entries))
	for _, e := range sc.entries {
		result = append(result, e)
	}
	return result
}
