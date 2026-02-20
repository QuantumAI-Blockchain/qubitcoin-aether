package compliance

import (
	"fmt"
	"sync"
)

// KYCRegistry manages KYC verification records for all addresses.
// This is the first layer of the three-layer compliance architecture.
//
// Tier limits (daily transaction volume):
//   - Retail:        $10,000/day  (10_000 * 10^8 QBC-units)
//   - Professional:  $1,000,000/day
//   - Institutional: Unlimited
//   - Sovereign:     Unlimited + custom policies
type KYCRegistry struct {
	mu      sync.RWMutex
	records map[[20]byte]*KYCStatus
}

// DailyLimits maps compliance tiers to daily transaction limits (in QBC base units).
// 0 = unlimited.
var DailyLimits = map[ComplianceTier]uint64{
	TierRetail:        10_000_00000000,    // $10K equivalent
	TierProfessional:  1_000_000_00000000, // $1M equivalent
	TierInstitutional: 0,                  // Unlimited
	TierSovereign:     0,                  // Unlimited
}

// NewKYCRegistry creates a new KYC registry.
func NewKYCRegistry() *KYCRegistry {
	return &KYCRegistry{
		records: make(map[[20]byte]*KYCStatus),
	}
}

// Register adds or updates a KYC record.
func (r *KYCRegistry) Register(status *KYCStatus) error {
	if status == nil {
		return fmt.Errorf("nil KYC status")
	}
	r.mu.Lock()
	defer r.mu.Unlock()
	r.records[status.Address] = status
	return nil
}

// GetStatus returns the KYC status for an address.
// Returns nil if the address is not registered.
func (r *KYCRegistry) GetStatus(addr [20]byte) *KYCStatus {
	r.mu.RLock()
	defer r.mu.RUnlock()
	return r.records[addr]
}

// IsVerified checks if an address has valid KYC at the given block.
func (r *KYCRegistry) IsVerified(addr [20]byte, currentBlock uint64) bool {
	r.mu.RLock()
	defer r.mu.RUnlock()

	status, ok := r.records[addr]
	if !ok || !status.Verified {
		return false
	}
	// Check expiration
	if status.ExpiresAt > 0 && currentBlock > status.ExpiresAt {
		return false
	}
	return true
}

// GetTier returns the compliance tier for an address.
// Returns TierRetail if not registered (default, most restrictive).
func (r *KYCRegistry) GetTier(addr [20]byte) ComplianceTier {
	r.mu.RLock()
	defer r.mu.RUnlock()

	status, ok := r.records[addr]
	if !ok {
		return TierRetail
	}
	return status.Tier
}

// GetDailyLimit returns the daily transaction limit for an address.
func (r *KYCRegistry) GetDailyLimit(addr [20]byte) uint64 {
	tier := r.GetTier(addr)
	return DailyLimits[tier]
}

// CheckTransactionAllowed validates whether an address can transact the given amount.
// Checks KYC status, tier limits, and expiration.
func (r *KYCRegistry) CheckTransactionAllowed(addr [20]byte, amount uint64, currentBlock uint64) *ComplianceResult {
	r.mu.RLock()
	defer r.mu.RUnlock()

	status, ok := r.records[addr]

	// Unregistered: default to retail with basic limits
	if !ok {
		limit := DailyLimits[TierRetail]
		if limit > 0 && amount > limit {
			return &ComplianceResult{
				Allowed:        false,
				Reason:         "exceeds retail daily limit; KYC required",
				Tier:           TierRetail,
				DailyRemaining: limit,
			}
		}
		return &ComplianceResult{
			Allowed:        true,
			Tier:           TierRetail,
			DailyRemaining: limit - amount,
		}
	}

	// Check expiration
	if status.ExpiresAt > 0 && currentBlock > status.ExpiresAt {
		return &ComplianceResult{
			Allowed: false,
			Reason:  "KYC verification expired",
			Tier:    status.Tier,
		}
	}

	// Check tier limits
	limit := DailyLimits[status.Tier]
	if limit > 0 && amount > limit {
		return &ComplianceResult{
			Allowed:        false,
			Reason:         fmt.Sprintf("exceeds %s daily limit", tierName(status.Tier)),
			Tier:           status.Tier,
			DailyRemaining: 0,
		}
	}

	remaining := uint64(0)
	if limit > 0 {
		remaining = limit - amount
	}

	return &ComplianceResult{
		Allowed:        true,
		Tier:           status.Tier,
		DailyRemaining: remaining,
	}
}

// Revoke removes KYC verification for an address.
func (r *KYCRegistry) Revoke(addr [20]byte) {
	r.mu.Lock()
	defer r.mu.Unlock()

	if status, ok := r.records[addr]; ok {
		status.Verified = false
	}
}

// Count returns the number of registered addresses.
func (r *KYCRegistry) Count() int {
	r.mu.RLock()
	defer r.mu.RUnlock()
	return len(r.records)
}

func tierName(t ComplianceTier) string {
	switch t {
	case TierRetail:
		return "Retail"
	case TierProfessional:
		return "Professional"
	case TierInstitutional:
		return "Institutional"
	case TierSovereign:
		return "Sovereign"
	default:
		return "Unknown"
	}
}
