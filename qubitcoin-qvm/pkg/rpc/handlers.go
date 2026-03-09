package rpc

import (
	"encoding/json"
	"fmt"
	"net/http"
	"runtime"
	"time"

	"go.uber.org/zap"
)

// Handlers implements all HTTP endpoint handlers for the QVM RPC server.
type Handlers struct {
	services  *ServiceRegistry
	logger    *zap.Logger
	startTime time.Time
}

// NewHandlers creates a new handlers instance.
func NewHandlers(services *ServiceRegistry, logger *zap.Logger) *Handlers {
	return &Handlers{
		services:  services,
		logger:    logger,
		startTime: time.Now(),
	}
}

// ─── Health & Readiness ───────────────────────────────────────────────

// Health returns a simple health check.
func (h *Handlers) Health(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, http.StatusOK, map[string]any{
		"status": "healthy",
		"uptime": time.Since(h.startTime).String(),
	})
}

// Ready returns readiness status (checks subsystem availability).
func (h *Handlers) Ready(w http.ResponseWriter, r *http.Request) {
	// Check if services are available
	ready := h.services != nil
	status := http.StatusOK
	if !ready {
		status = http.StatusServiceUnavailable
	}
	writeJSON(w, status, map[string]any{
		"ready": ready,
	})
}

// ─── Node Info ────────────────────────────────────────────────────────

// NodeInfo returns general node information.
func (h *Handlers) NodeInfo(w http.ResponseWriter, r *http.Request) {
	var blockHeight uint64
	if h.services != nil && h.services.BlockHeight != nil {
		blockHeight = h.services.BlockHeight()
	}

	version := "0.1.0"
	if h.services != nil && h.services.Version != "" {
		version = h.services.Version
	}

	chainID := uint64(3303)
	if h.services != nil && h.services.ChainID > 0 {
		chainID = h.services.ChainID
	}

	writeJSON(w, http.StatusOK, map[string]any{
		"name":         "Qubitcoin QVM",
		"version":      version,
		"chain_id":     chainID,
		"block_height": blockHeight,
		"uptime":       time.Since(h.startTime).String(),
		"go_version":   runtime.Version(),
		"os":           runtime.GOOS,
		"arch":         runtime.GOARCH,
		"features": []string{
			"evm_compatible",
			"quantum_opcodes",
			"compliance_engine",
			"plugin_system",
			"post_quantum_crypto",
		},
	})
}

// ─── Chain Info ───────────────────────────────────────────────────────

// ChainInfo returns blockchain statistics.
func (h *Handlers) ChainInfo(w http.ResponseWriter, r *http.Request) {
	var blockHeight uint64
	if h.services != nil && h.services.BlockHeight != nil {
		blockHeight = h.services.BlockHeight()
	}

	chainID := uint64(3303)
	if h.services != nil && h.services.ChainID > 0 {
		chainID = h.services.ChainID
	}

	writeJSON(w, http.StatusOK, map[string]any{
		"chain_id":          chainID,
		"chain_name":        "Qubitcoin Mainnet",
		"block_height":      blockHeight,
		"target_block_time": 3.3,
		"consensus":         "Proof-of-SUSY-Alignment",
		"max_supply":        "3300000000",
		"block_gas_limit":   30_000_000,
		"quantum_opcodes":   10,
		"evm_opcodes":       155,
	})
}

// ─── QVM Info ─────────────────────────────────────────────────────────

// QVMInfo returns QVM engine information.
func (h *Handlers) QVMInfo(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, http.StatusOK, map[string]any{
		"engine":             "qubitcoin-qvm",
		"implementation":     "go",
		"evm_opcodes":        155,
		"quantum_opcodes":    10,
		"quantum_opcode_range": "0xC0-0xDE",
		"max_stack_depth":    1024,
		"block_gas_limit":    30_000_000,
		"max_code_size":      24576,
		"max_init_code_size": 49152,
		"precompiles":        "0x01-0x09",
		"compliance_tiers": []string{
			"retail",
			"professional",
			"institutional",
			"sovereign",
		},
		"plugin_types": []string{
			"privacy",
			"oracle",
			"governance",
			"defi",
		},
		"patents": []string{
			"QSP (Quantum State Persistence)",
			"ESCC (Entanglement-Based Communication)",
			"PCP (Programmable Compliance Policies)",
			"RRAO (Real-Time Risk Assessment)",
			"QVCSP (Quantum-Verified Cross-Chain Proofs)",
		},
	})
}

// ─── Metrics ──────────────────────────────────────────────────────────

// Metrics returns Prometheus-format metrics.
func (h *Handlers) Metrics(w http.ResponseWriter, r *http.Request) {
	var blockHeight uint64
	if h.services != nil && h.services.BlockHeight != nil {
		blockHeight = h.services.BlockHeight()
	}

	w.Header().Set("Content-Type", "text/plain; version=0.0.4")
	fmt.Fprintf(w, "# HELP qvm_block_height Current block height\n")
	fmt.Fprintf(w, "# TYPE qvm_block_height gauge\n")
	fmt.Fprintf(w, "qvm_block_height %d\n", blockHeight)
	fmt.Fprintf(w, "# HELP qvm_uptime_seconds QVM uptime in seconds\n")
	fmt.Fprintf(w, "# TYPE qvm_uptime_seconds gauge\n")
	fmt.Fprintf(w, "qvm_uptime_seconds %.2f\n", time.Since(h.startTime).Seconds())
	fmt.Fprintf(w, "# HELP qvm_goroutines Number of goroutines\n")
	fmt.Fprintf(w, "# TYPE qvm_goroutines gauge\n")
	fmt.Fprintf(w, "qvm_goroutines %d\n", runtime.NumGoroutine())
}

// ─── Helpers ──────────────────────────────────────────────────────────

func writeJSON(w http.ResponseWriter, status int, data any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	json.NewEncoder(w).Encode(data)
}

func writeError(w http.ResponseWriter, status int, message string) {
	writeJSON(w, status, map[string]any{
		"error":   true,
		"message": message,
	})
}
