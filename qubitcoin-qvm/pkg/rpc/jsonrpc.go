package rpc

import (
	"encoding/json"
	"fmt"
	"io"
	"net/http"

	"go.uber.org/zap"
)

// JSONRPCRequest represents an incoming JSON-RPC 2.0 request.
type JSONRPCRequest struct {
	JSONRPC string          `json:"jsonrpc"`
	Method  string          `json:"method"`
	Params  json.RawMessage `json:"params,omitempty"`
	ID      any             `json:"id"`
}

// JSONRPCResponse represents an outgoing JSON-RPC 2.0 response.
type JSONRPCResponse struct {
	JSONRPC string      `json:"jsonrpc"`
	Result  any         `json:"result,omitempty"`
	Error   *RPCError   `json:"error,omitempty"`
	ID      any         `json:"id"`
}

// RPCError represents a JSON-RPC error.
type RPCError struct {
	Code    int    `json:"code"`
	Message string `json:"message"`
	Data    any    `json:"data,omitempty"`
}

// Standard JSON-RPC error codes.
const (
	ErrCodeParse          = -32700
	ErrCodeInvalidRequest = -32600
	ErrCodeMethodNotFound = -32601
	ErrCodeInvalidParams  = -32602
	ErrCodeInternal       = -32603
)

// JSONRPCHandler handles JSON-RPC 2.0 requests (eth_* compatible for MetaMask/Web3).
func (h *Handlers) JSONRPCHandler(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		writeError(w, http.StatusMethodNotAllowed, "POST required")
		return
	}

	body, err := io.ReadAll(r.Body)
	if err != nil {
		writeJSONRPC(w, nil, &RPCError{Code: ErrCodeParse, Message: "failed to read request"})
		return
	}

	// Try batch request first
	var batch []JSONRPCRequest
	if err := json.Unmarshal(body, &batch); err == nil && len(batch) > 0 {
		responses := make([]JSONRPCResponse, len(batch))
		for i, req := range batch {
			responses[i] = h.dispatchRPC(req)
		}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(responses)
		return
	}

	// Single request
	var req JSONRPCRequest
	if err := json.Unmarshal(body, &req); err != nil {
		writeJSONRPC(w, nil, &RPCError{Code: ErrCodeParse, Message: "invalid JSON"})
		return
	}

	resp := h.dispatchRPC(req)
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(resp)
}

// dispatchRPC routes a JSON-RPC request to the appropriate handler.
func (h *Handlers) dispatchRPC(req JSONRPCRequest) JSONRPCResponse {
	if req.JSONRPC != "2.0" {
		return JSONRPCResponse{
			JSONRPC: "2.0",
			Error:   &RPCError{Code: ErrCodeInvalidRequest, Message: "jsonrpc must be 2.0"},
			ID:      req.ID,
		}
	}

	h.logger.Debug("JSON-RPC request", zap.String("method", req.Method))

	var result any
	var rpcErr *RPCError

	switch req.Method {
	// ── Chain ──────────────────────────────────────────────────────
	case "eth_chainId":
		chainID := uint64(3301)
		if h.services != nil && h.services.ChainID > 0 {
			chainID = h.services.ChainID
		}
		result = fmt.Sprintf("0x%x", chainID)

	case "net_version":
		chainID := uint64(3301)
		if h.services != nil && h.services.ChainID > 0 {
			chainID = h.services.ChainID
		}
		result = fmt.Sprintf("%d", chainID)

	case "eth_blockNumber":
		var height uint64
		if h.services != nil && h.services.BlockHeight != nil {
			height = h.services.BlockHeight()
		}
		result = fmt.Sprintf("0x%x", height)

	case "web3_clientVersion":
		version := "QubitcoinQVM/0.1.0"
		if h.services != nil && h.services.Version != "" {
			version = "QubitcoinQVM/" + h.services.Version
		}
		result = version

	case "web3_sha3":
		// Keccak-256 hash of input data
		var params []string
		if err := json.Unmarshal(req.Params, &params); err != nil || len(params) == 0 {
			rpcErr = &RPCError{Code: ErrCodeInvalidParams, Message: "expected [hexData]"}
		} else {
			// Placeholder: return hash of input
			result = "0x" + "0000000000000000000000000000000000000000000000000000000000000000"
		}

	// ── Account ───────────────────────────────────────────────────
	case "eth_getBalance":
		// params: [address, blockTag]
		// Stub: return 0 balance
		result = "0x0"

	case "eth_getTransactionCount":
		// params: [address, blockTag]
		// Stub: return 0 nonce
		result = "0x0"

	case "eth_getCode":
		// params: [address, blockTag]
		// Stub: return empty code
		result = "0x"

	case "eth_getStorageAt":
		// params: [address, position, blockTag]
		result = "0x0000000000000000000000000000000000000000000000000000000000000000"

	// ── Block ─────────────────────────────────────────────────────
	case "eth_getBlockByNumber":
		// Stub: return minimal block
		var height uint64
		if h.services != nil && h.services.BlockHeight != nil {
			height = h.services.BlockHeight()
		}
		result = map[string]any{
			"number":     fmt.Sprintf("0x%x", height),
			"hash":       "0x" + "0000000000000000000000000000000000000000000000000000000000000000",
			"parentHash": "0x" + "0000000000000000000000000000000000000000000000000000000000000000",
			"timestamp":  "0x0",
			"gasLimit":   "0x1c9c380", // 30,000,000
			"gasUsed":    "0x0",
			"miner":      "0x" + "0000000000000000000000000000000000000000",
			"transactions": []any{},
		}

	case "eth_getBlockByHash":
		// Stub: same as getBlockByNumber
		result = map[string]any{
			"number":       "0x0",
			"hash":         "0x" + "0000000000000000000000000000000000000000000000000000000000000000",
			"transactions": []any{},
		}

	// ── Transaction ───────────────────────────────────────────────
	case "eth_sendRawTransaction":
		// Stub: not yet implemented
		rpcErr = &RPCError{Code: ErrCodeInternal, Message: "not yet implemented"}

	case "eth_call":
		// params: [{to, data, ...}, blockTag]
		// Stub: return empty data
		result = "0x"

	case "eth_estimateGas":
		// Stub: return 21000 (basic transfer)
		result = "0x5208"

	case "eth_gasPrice":
		// Return default gas price (1 Gwei equivalent)
		result = "0x3b9aca00"

	case "eth_maxPriorityFeePerGas":
		result = "0x3b9aca00"

	case "eth_feeHistory":
		result = map[string]any{
			"oldestBlock":   "0x0",
			"baseFeePerGas": []string{"0x3b9aca00"},
			"gasUsedRatio":  []float64{0.0},
		}

	// ── Network ───────────────────────────────────────────────────
	case "net_listening":
		result = true

	case "net_peerCount":
		result = "0x0"

	case "eth_syncing":
		result = false

	case "eth_mining":
		result = false

	case "eth_accounts":
		result = []string{}

	// ── Filter (stubs) ────────────────────────────────────────────
	case "eth_newFilter", "eth_newBlockFilter", "eth_newPendingTransactionFilter":
		result = "0x1"

	case "eth_getFilterChanges", "eth_getFilterLogs":
		result = []any{}

	case "eth_uninstallFilter":
		result = true

	case "eth_getLogs":
		result = []any{}

	default:
		rpcErr = &RPCError{
			Code:    ErrCodeMethodNotFound,
			Message: fmt.Sprintf("method %q not found", req.Method),
		}
	}

	return JSONRPCResponse{
		JSONRPC: "2.0",
		Result:  result,
		Error:   rpcErr,
		ID:      req.ID,
	}
}

func writeJSONRPC(w http.ResponseWriter, id any, rpcErr *RPCError) {
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(JSONRPCResponse{
		JSONRPC: "2.0",
		Error:   rpcErr,
		ID:      id,
	})
}
