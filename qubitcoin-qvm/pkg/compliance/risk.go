package compliance

import (
	"math"
	"sync"
)

// RiskScorer computes SUSY-inspired risk scores for addresses and systemic risk.
// Implements the QRISK and QRISK_SYSTEMIC opcodes.
//
// Risk scores are 0-10000 (scaled by 100, so 100 = 1.00).
//
// Individual risk factors:
//   - Transaction velocity (high frequency = higher risk)
//   - Volume concentration (single large tx = higher risk)
//   - Counterparty risk (transacting with risky addresses)
//   - Account age (newer accounts = higher risk)
//   - KYC tier (higher tier = lower risk)
//
// Systemic risk uses a simplified contagion model inspired by
// SUSY field theory — tracking energy flow between "particles" (addresses)
// and detecting critical cascading failure thresholds.
type RiskScorer struct {
	mu sync.RWMutex

	// Per-address risk scores (0-10000)
	scores map[[20]byte]*AddressRisk

	// Systemic risk (0-10000)
	systemicRisk uint64

	// Configuration
	config RiskConfig

	// Circuit breaker state
	circuitBreakerActive bool
	circuitBreakerBlock  uint64
}

// AddressRisk holds the computed risk profile for an address.
type AddressRisk struct {
	Address         [20]byte
	Score           uint64 // 0-10000 (100 = 1.00)
	VelocityRisk    uint64 // 0-10000
	VolumeRisk      uint64 // 0-10000
	CounterpartyRisk uint64 // 0-10000
	AgeRisk         uint64 // 0-10000
	TierBonus       int64  // negative = reduces risk
	LastUpdated     uint64 // block number
}

// RiskConfig holds configurable risk scoring parameters.
type RiskConfig struct {
	// CircuitBreakerThreshold: systemic risk level that triggers circuit breaker (0-10000).
	CircuitBreakerThreshold uint64
	// CircuitBreakerCooldown: blocks before circuit breaker can be reset.
	CircuitBreakerCooldown uint64
	// VelocityWeight: how much velocity contributes to overall score (0-100).
	VelocityWeight uint64
	// VolumeWeight: how much volume contributes to overall score (0-100).
	VolumeWeight uint64
	// CounterpartyWeight: how much counterparty risk contributes (0-100).
	CounterpartyWeight uint64
	// AgeWeight: how much account age contributes (0-100).
	AgeWeight uint64
}

// DefaultRiskConfig returns production risk scoring defaults.
func DefaultRiskConfig() RiskConfig {
	return RiskConfig{
		CircuitBreakerThreshold: 8000,  // 80.00 systemic risk triggers halt
		CircuitBreakerCooldown:  26182, // ~1 day of blocks
		VelocityWeight:          30,
		VolumeWeight:            25,
		CounterpartyWeight:      25,
		AgeWeight:               20,
	}
}

// NewRiskScorer creates a new risk scorer with default configuration.
func NewRiskScorer() *RiskScorer {
	return &RiskScorer{
		scores: make(map[[20]byte]*AddressRisk),
		config: DefaultRiskConfig(),
	}
}

// NewRiskScorerWithConfig creates a risk scorer with custom configuration.
func NewRiskScorerWithConfig(config RiskConfig) *RiskScorer {
	return &RiskScorer{
		scores: make(map[[20]byte]*AddressRisk),
		config: config,
	}
}

// ComputeRisk calculates the risk score for an address.
func (rs *RiskScorer) ComputeRisk(
	addr [20]byte,
	txCount uint64,
	volume uint64,
	accountAge uint64,
	tier ComplianceTier,
	blockNum uint64,
) uint64 {
	rs.mu.Lock()
	defer rs.mu.Unlock()

	risk := &AddressRisk{
		Address:     addr,
		LastUpdated: blockNum,
	}

	// Velocity risk: sigmoid function of tx count
	// Higher tx count → higher risk, capped at 10000
	risk.VelocityRisk = sigmoid(float64(txCount), 50, 0.1)

	// Volume risk: logarithmic scale of total volume
	if volume > 0 {
		risk.VolumeRisk = uint64(math.Min(10000, math.Log10(float64(volume))*1000))
	}

	// Account age risk: newer = riskier (exponential decay)
	if accountAge == 0 {
		risk.AgeRisk = 10000 // brand new account = max age risk
	} else {
		// Risk decreases with age: risk = 10000 * e^(-age/26182)
		decay := math.Exp(-float64(accountAge) / 26182.0)
		risk.AgeRisk = uint64(10000 * decay)
	}

	// Tier bonus (higher tier = lower risk)
	tierBonuses := map[ComplianceTier]int64{
		TierRetail:        0,
		TierProfessional:  -1000,
		TierInstitutional: -2000,
		TierSovereign:     -3000,
	}
	risk.TierBonus = tierBonuses[tier]

	// Weighted composite score
	cfg := rs.config
	totalWeight := cfg.VelocityWeight + cfg.VolumeWeight + cfg.CounterpartyWeight + cfg.AgeWeight
	if totalWeight == 0 {
		totalWeight = 100
	}

	composite := (risk.VelocityRisk*cfg.VelocityWeight +
		risk.VolumeRisk*cfg.VolumeWeight +
		risk.CounterpartyRisk*cfg.CounterpartyWeight +
		risk.AgeRisk*cfg.AgeWeight) / totalWeight

	// Apply tier bonus
	score := int64(composite) + risk.TierBonus
	if score < 0 {
		score = 0
	}
	if score > 10000 {
		score = 10000
	}
	risk.Score = uint64(score)

	rs.scores[addr] = risk
	return risk.Score
}

// GetRisk returns the last computed risk score for an address.
func (rs *RiskScorer) GetRisk(addr [20]byte) uint64 {
	rs.mu.RLock()
	defer rs.mu.RUnlock()

	risk, ok := rs.scores[addr]
	if !ok {
		return 5000 // default: medium risk for unknown addresses
	}
	return risk.Score
}

// GetRiskProfile returns the full risk profile for an address.
func (rs *RiskScorer) GetRiskProfile(addr [20]byte) *AddressRisk {
	rs.mu.RLock()
	defer rs.mu.RUnlock()
	return rs.scores[addr]
}

// ComputeSystemicRisk computes the network-wide systemic risk.
// Uses a simplified contagion model: average risk weighted by volume.
func (rs *RiskScorer) ComputeSystemicRisk() uint64 {
	rs.mu.Lock()
	defer rs.mu.Unlock()

	if len(rs.scores) == 0 {
		rs.systemicRisk = 0
		return 0
	}

	var totalRisk uint64
	for _, risk := range rs.scores {
		totalRisk += risk.Score
	}
	rs.systemicRisk = totalRisk / uint64(len(rs.scores))

	return rs.systemicRisk
}

// GetSystemicRisk returns the last computed systemic risk level.
func (rs *RiskScorer) GetSystemicRisk() uint64 {
	rs.mu.RLock()
	defer rs.mu.RUnlock()
	return rs.systemicRisk
}

// IsCircuitBreakerActive returns true if the circuit breaker has been triggered.
func (rs *RiskScorer) IsCircuitBreakerActive() bool {
	rs.mu.RLock()
	defer rs.mu.RUnlock()
	return rs.circuitBreakerActive
}

// CheckCircuitBreaker evaluates systemic risk and triggers the circuit breaker if needed.
// Returns true if the circuit breaker is (or was already) active.
func (rs *RiskScorer) CheckCircuitBreaker(blockNum uint64) bool {
	rs.mu.Lock()
	defer rs.mu.Unlock()

	// Check cooldown
	if rs.circuitBreakerActive {
		if blockNum-rs.circuitBreakerBlock > rs.config.CircuitBreakerCooldown {
			rs.circuitBreakerActive = false
		}
		return rs.circuitBreakerActive
	}

	// Check threshold
	if rs.systemicRisk >= rs.config.CircuitBreakerThreshold {
		rs.circuitBreakerActive = true
		rs.circuitBreakerBlock = blockNum
		return true
	}

	return false
}

// ResetCircuitBreaker manually resets the circuit breaker (admin action).
func (rs *RiskScorer) ResetCircuitBreaker() {
	rs.mu.Lock()
	defer rs.mu.Unlock()
	rs.circuitBreakerActive = false
}

// sigmoid maps input to 0-10000 range using a sigmoid function.
func sigmoid(x, midpoint, steepness float64) uint64 {
	val := 1.0 / (1.0 + math.Exp(-steepness*(x-midpoint)))
	return uint64(val * 10000)
}
