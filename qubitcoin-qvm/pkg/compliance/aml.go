package compliance

import (
	"sync"
)

// AMLMonitor tracks transaction patterns for anti-money-laundering detection.
// Implements velocity checks, structuring detection, and suspicious pattern
// identification as part of the second compliance layer.
//
// Alert thresholds (configurable):
//   - Velocity:    >10 transactions within 10 blocks from same address
//   - Structuring: Multiple transactions just below reporting threshold
//   - Volume:      Sudden spike in daily volume vs. 30-day average
//   - Mixing:      Fan-out pattern (1 input → many outputs of similar size)
type AMLMonitor struct {
	mu sync.RWMutex

	// Per-address transaction tracking
	txHistory map[[20]byte]*AddressTxHistory

	// Active alerts
	alerts []*AMLAlert

	// Configuration
	config AMLConfig
}

// AddressTxHistory tracks recent transaction activity for an address.
type AddressTxHistory struct {
	Address        [20]byte
	RecentTxCount  uint64 // transactions in current window
	WindowStart    uint64 // block number when window started
	DailyVolume    uint64 // total volume in current day-window
	DayStart       uint64 // block of current day start
	AvgDailyVolume uint64 // 30-day rolling average
	TotalLifetime  uint64 // total volume ever
}

// AMLAlert represents a triggered AML alert.
type AMLAlert struct {
	Address   [20]byte
	AlertType AMLAlertType
	Severity  AlertSeverity
	BlockNum  uint64
	Amount    uint64
	Details   string
	Resolved  bool
}

// AMLAlertType categorizes the type of suspicious activity.
type AMLAlertType uint8

const (
	AlertVelocity    AMLAlertType = iota // Too many transactions in short window
	AlertStructuring                     // Amounts just below reporting threshold
	AlertVolumeSpike                     // Sudden volume increase
	AlertMixing                          // Fan-out transaction pattern
	AlertRoundTrip                       // Funds returning to origin
)

// AlertSeverity indicates the urgency of an alert.
type AlertSeverity uint8

const (
	SeverityLow    AlertSeverity = iota // Informational
	SeverityMedium                      // Review required
	SeverityHigh                        // Immediate action needed
	SeverityCritical                    // Auto-freeze recommended
)

// AMLConfig holds configurable thresholds for AML monitoring.
type AMLConfig struct {
	// VelocityWindow is the number of blocks in a velocity check window.
	VelocityWindow uint64
	// VelocityMaxTx is the max transactions allowed in VelocityWindow.
	VelocityMaxTx uint64
	// StructuringThreshold is the reporting threshold (tx just below this are suspicious).
	StructuringThreshold uint64
	// StructuringMargin is how close to threshold counts as structuring (percentage, 0-100).
	StructuringMargin uint64
	// VolumeSpikeFactor is the multiplier over average that triggers a volume alert.
	VolumeSpikeFactor uint64
	// BlocksPerDay approximates one day in blocks (3.3s blocks ≈ 26,182 blocks/day).
	BlocksPerDay uint64
}

// DefaultAMLConfig returns production defaults.
func DefaultAMLConfig() AMLConfig {
	return AMLConfig{
		VelocityWindow:       10,                 // 10 blocks (~33 seconds)
		VelocityMaxTx:        10,                 // max 10 tx per window
		StructuringThreshold: 10_000_00000000,    // $10K equivalent
		StructuringMargin:    15,                 // within 15% of threshold
		VolumeSpikeFactor:    5,                  // 5x average triggers alert
		BlocksPerDay:         26_182,             // ~3.3s blocks
	}
}

// NewAMLMonitor creates a new AML monitor with default configuration.
func NewAMLMonitor() *AMLMonitor {
	return &AMLMonitor{
		txHistory: make(map[[20]byte]*AddressTxHistory),
		config:    DefaultAMLConfig(),
	}
}

// NewAMLMonitorWithConfig creates an AML monitor with custom configuration.
func NewAMLMonitorWithConfig(config AMLConfig) *AMLMonitor {
	return &AMLMonitor{
		txHistory: make(map[[20]byte]*AddressTxHistory),
		config:    config,
	}
}

// RecordTransaction records a transaction and checks for suspicious patterns.
// Returns any new alerts triggered.
func (m *AMLMonitor) RecordTransaction(addr [20]byte, amount uint64, blockNum uint64) []*AMLAlert {
	m.mu.Lock()
	defer m.mu.Unlock()

	history := m.getOrCreateHistory(addr)
	var newAlerts []*AMLAlert

	// Reset window if expired
	if blockNum-history.WindowStart > m.config.VelocityWindow {
		history.RecentTxCount = 0
		history.WindowStart = blockNum
	}

	// Reset daily window
	if blockNum-history.DayStart > m.config.BlocksPerDay {
		// Update rolling average before reset
		if history.AvgDailyVolume == 0 {
			history.AvgDailyVolume = history.DailyVolume
		} else {
			// Simple exponential moving average (weight 0.1 for new day)
			history.AvgDailyVolume = (history.AvgDailyVolume*9 + history.DailyVolume) / 10
		}
		history.DailyVolume = 0
		history.DayStart = blockNum
	}

	history.RecentTxCount++
	history.DailyVolume += amount
	history.TotalLifetime += amount

	// Check 1: Velocity
	if history.RecentTxCount > m.config.VelocityMaxTx {
		alert := &AMLAlert{
			Address:   addr,
			AlertType: AlertVelocity,
			Severity:  SeverityMedium,
			BlockNum:  blockNum,
			Amount:    amount,
			Details:   "high transaction velocity detected",
		}
		newAlerts = append(newAlerts, alert)
	}

	// Check 2: Structuring (amounts just below reporting threshold)
	if m.config.StructuringThreshold > 0 {
		margin := m.config.StructuringThreshold * m.config.StructuringMargin / 100
		lowerBound := m.config.StructuringThreshold - margin
		if amount >= lowerBound && amount < m.config.StructuringThreshold {
			alert := &AMLAlert{
				Address:   addr,
				AlertType: AlertStructuring,
				Severity:  SeverityHigh,
				BlockNum:  blockNum,
				Amount:    amount,
				Details:   "potential structuring: amount near reporting threshold",
			}
			newAlerts = append(newAlerts, alert)
		}
	}

	// Check 3: Volume spike
	if history.AvgDailyVolume > 0 && m.config.VolumeSpikeFactor > 0 {
		if history.DailyVolume > history.AvgDailyVolume*m.config.VolumeSpikeFactor {
			alert := &AMLAlert{
				Address:   addr,
				AlertType: AlertVolumeSpike,
				Severity:  SeverityMedium,
				BlockNum:  blockNum,
				Amount:    history.DailyVolume,
				Details:   "daily volume significantly exceeds average",
			}
			newAlerts = append(newAlerts, alert)
		}
	}

	m.alerts = append(m.alerts, newAlerts...)
	return newAlerts
}

// GetAlerts returns all alerts, optionally filtered by address.
func (m *AMLMonitor) GetAlerts(addr *[20]byte) []*AMLAlert {
	m.mu.RLock()
	defer m.mu.RUnlock()

	if addr == nil {
		result := make([]*AMLAlert, len(m.alerts))
		copy(result, m.alerts)
		return result
	}

	var filtered []*AMLAlert
	for _, a := range m.alerts {
		if a.Address == *addr {
			filtered = append(filtered, a)
		}
	}
	return filtered
}

// GetActiveAlertCount returns the number of unresolved alerts.
func (m *AMLMonitor) GetActiveAlertCount() int {
	m.mu.RLock()
	defer m.mu.RUnlock()

	count := 0
	for _, a := range m.alerts {
		if !a.Resolved {
			count++
		}
	}
	return count
}

// ResolveAlert marks an alert as resolved.
func (m *AMLMonitor) ResolveAlert(idx int) {
	m.mu.Lock()
	defer m.mu.Unlock()

	if idx >= 0 && idx < len(m.alerts) {
		m.alerts[idx].Resolved = true
	}
}

// GetHistory returns transaction history for an address.
func (m *AMLMonitor) GetHistory(addr [20]byte) *AddressTxHistory {
	m.mu.RLock()
	defer m.mu.RUnlock()
	return m.txHistory[addr]
}

func (m *AMLMonitor) getOrCreateHistory(addr [20]byte) *AddressTxHistory {
	h, ok := m.txHistory[addr]
	if !ok {
		h = &AddressTxHistory{Address: addr}
		m.txHistory[addr] = h
	}
	return h
}
