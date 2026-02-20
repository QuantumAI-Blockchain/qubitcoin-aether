// Package compliance implements the QVM compliance engine.
//
// Provides three-layer compliance architecture:
//   1. Policy Layer — Programmable rules (tx limits, KYC requirements, sanctions)
//   2. Verification Layer — Quantum-verified compliance checks
//   3. Reporting Layer — Automated regulatory reports (MiCA, SEC, FinCEN)
//
// Key features:
//   - QCOMPLIANCE opcode — Pre-flight compliance check before tx execution
//   - ERC-20-QC standard — Compliance-aware token standard
//   - Risk scoring (QRISK) — SUSY Hamiltonian-based risk assessment
//   - Auto-circuit breakers — Halt when systemic risk exceeds threshold
//   - TLAC — Time-Locked Atomic Compliance (multi-jurisdictional)
//   - HDCK — Hierarchical Deterministic Compliance Keys (BIP-32 extension)
//   - VCR — Verifiable Computation Receipts (quantum audit trails)
package compliance

// ComplianceTier defines the compliance level for an address.
type ComplianceTier int

const (
	// TierRetail — Basic KYC, $10K/day limits, free.
	TierRetail ComplianceTier = iota
	// TierProfessional — Enhanced KYC, $1M/day, AML monitoring. $500/mo.
	TierProfessional
	// TierInstitutional — Full KYC, unlimited, quantum verification. $5,000/mo.
	TierInstitutional
	// TierSovereign — Central bank, custom policies, SUSY risk. $50,000/mo.
	TierSovereign
)

// KYCStatus represents an address's KYC verification status.
type KYCStatus struct {
	Address    [20]byte
	Tier       ComplianceTier
	Verified   bool
	VerifiedAt uint64 // block number
	ExpiresAt  uint64 // block number (0 = never)
	Provider   string // KYC provider ID
}

// ComplianceResult is returned by the QCOMPLIANCE opcode.
type ComplianceResult struct {
	Allowed       bool
	Reason        string
	RiskScore     uint64
	Tier          ComplianceTier
	DailyRemaining uint64 // remaining daily limit in QBC
}

// SanctionsEntry represents an entry on the sanctions list.
type SanctionsEntry struct {
	Address  [20]byte
	ListedAt uint64
	Source   string // OFAC, EU, UN, etc.
	Active   bool
}
