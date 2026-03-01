package rpc

import (
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strings"

	"github.com/BlockArtica/qubitcoin-qvm/pkg/crypto"
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
		// Keccak-256 hash of input data (EIP-191)
		var params []string
		if err := json.Unmarshal(req.Params, &params); err != nil || len(params) == 0 {
			rpcErr = &RPCError{Code: ErrCodeInvalidParams, Message: "expected [hexData]"}
		} else {
			input := strings.TrimPrefix(params[0], "0x")
			data, decErr := hex.DecodeString(input)
			if decErr != nil {
				rpcErr = &RPCError{Code: ErrCodeInvalidParams, Message: "invalid hex data"}
			} else {
				hash := crypto.Keccak256(data)
				result = "0x" + hex.EncodeToString(hash[:])
			}
		}

	// ── Account ───────────────────────────────────────────────────
	case "eth_getBalance":
		// params: [address, blockTag]
		var params []string
		if err := json.Unmarshal(req.Params, &params); err != nil || len(params) == 0 {
			rpcErr = &RPCError{Code: ErrCodeInvalidParams, Message: "expected [address, blockTag]"}
		} else if h.services != nil && h.services.State != nil {
			addr := parseAddress(params[0])
			balance := h.services.State.GetBalance(addr)
			result = "0x" + balance.Text(16)
		} else {
			result = "0x0"
		}

	case "eth_getTransactionCount":
		// params: [address, blockTag]
		var params []string
		if err := json.Unmarshal(req.Params, &params); err != nil || len(params) == 0 {
			rpcErr = &RPCError{Code: ErrCodeInvalidParams, Message: "expected [address, blockTag]"}
		} else if h.services != nil && h.services.State != nil {
			addr := parseAddress(params[0])
			nonce := h.services.State.GetNonce(addr)
			result = fmt.Sprintf("0x%x", nonce)
		} else {
			result = "0x0"
		}

	case "eth_getCode":
		// params: [address, blockTag]
		var params []string
		if err := json.Unmarshal(req.Params, &params); err != nil || len(params) == 0 {
			rpcErr = &RPCError{Code: ErrCodeInvalidParams, Message: "expected [address, blockTag]"}
		} else if h.services != nil && h.services.State != nil {
			addr := parseAddress(params[0])
			code := h.services.State.GetCode(addr)
			result = "0x" + hex.EncodeToString(code)
		} else {
			result = "0x"
		}

	case "eth_getStorageAt":
		// params: [address, position, blockTag]
		var params []string
		if err := json.Unmarshal(req.Params, &params); err != nil || len(params) < 2 {
			rpcErr = &RPCError{Code: ErrCodeInvalidParams, Message: "expected [address, position, blockTag]"}
		} else if h.services != nil && h.services.State != nil {
			addr := parseAddress(params[0])
			key := parseHash(params[1])
			val := h.services.State.GetStorage(addr, key)
			result = "0x" + hex.EncodeToString(val[:])
		} else {
			result = "0x0000000000000000000000000000000000000000000000000000000000000000"
		}

	// ── Block ─────────────────────────────────────────────────────
	case "eth_getBlockByNumber":
		var params []json.RawMessage
		if err := json.Unmarshal(req.Params, &params); err != nil || len(params) == 0 {
			rpcErr = &RPCError{Code: ErrCodeInvalidParams, Message: "expected [blockNumber, fullTx]"}
		} else {
			var blockNum string
			json.Unmarshal(params[0], &blockNum)
			height := resolveBlockNumber(blockNum, h.services)
			result = h.buildBlockResponse(height)
		}

	case "eth_getBlockByHash":
		var params []json.RawMessage
		if err := json.Unmarshal(req.Params, &params); err != nil || len(params) == 0 {
			rpcErr = &RPCError{Code: ErrCodeInvalidParams, Message: "expected [blockHash, fullTx]"}
		} else {
			var hashStr string
			json.Unmarshal(params[0], &hashStr)
			if h.services != nil && h.services.BlockStore != nil {
				bHash := parseHash(hashStr)
				if blk, err := h.services.BlockStore.GetBlockByHash(bHash); err == nil && blk != nil {
					result = formatBlock(blk)
				} else {
					result = nil
				}
			} else {
				result = nil
			}
		}

	// ── Transaction ───────────────────────────────────────────────
	case "eth_sendRawTransaction":
		var params []string
		if err := json.Unmarshal(req.Params, &params); err != nil || len(params) == 0 {
			rpcErr = &RPCError{Code: ErrCodeInvalidParams, Message: "expected [signedTxData]"}
		} else if h.services != nil && h.services.TxPool != nil {
			rawTx := strings.TrimPrefix(params[0], "0x")
			txBytes, decErr := hex.DecodeString(rawTx)
			if decErr != nil {
				rpcErr = &RPCError{Code: ErrCodeInvalidParams, Message: "invalid hex transaction data"}
			} else {
				txHash, submitErr := h.services.TxPool.SubmitRawTransaction(txBytes)
				if submitErr != nil {
					rpcErr = &RPCError{Code: ErrCodeInternal, Message: submitErr.Error()}
				} else {
					result = "0x" + hex.EncodeToString(txHash[:])
				}
			}
		} else {
			rpcErr = &RPCError{Code: ErrCodeInternal, Message: "transaction pool not available"}
		}

	case "eth_call":
		var params []json.RawMessage
		if err := json.Unmarshal(req.Params, &params); err != nil || len(params) == 0 {
			rpcErr = &RPCError{Code: ErrCodeInvalidParams, Message: "expected [{to, data, from, gas}, blockTag]"}
		} else {
			var callObj struct {
				From string `json:"from"`
				To   string `json:"to"`
				Data string `json:"data"`
				Gas  string `json:"gas"`
			}
			if err := json.Unmarshal(params[0], &callObj); err != nil {
				rpcErr = &RPCError{Code: ErrCodeInvalidParams, Message: "invalid call object"}
			} else if h.services != nil && h.services.VM != nil {
				from := parseAddress(callObj.From)
				to := parseAddress(callObj.To)
				input := strings.TrimPrefix(callObj.Data, "0x")
				data, _ := hex.DecodeString(input)
				var gas uint64 = DefaultGasLimit
				if callObj.Gas != "" {
					fmt.Sscanf(strings.TrimPrefix(callObj.Gas, "0x"), "%x", &gas)
				}
				retData, _, callErr := h.services.VM.StaticCall(from, to, data, gas)
				if callErr != nil {
					rpcErr = &RPCError{Code: ErrCodeInternal, Message: callErr.Error()}
				} else {
					result = "0x" + hex.EncodeToString(retData)
				}
			} else {
				result = "0x"
			}
		}

	case "eth_estimateGas":
		var params []json.RawMessage
		if err := json.Unmarshal(req.Params, &params); err != nil || len(params) == 0 {
			result = "0x5208" // default: 21000 for simple transfer
		} else {
			var callObj struct {
				From string `json:"from"`
				To   string `json:"to"`
				Data string `json:"data"`
			}
			if err := json.Unmarshal(params[0], &callObj); err != nil {
				result = "0x5208"
			} else if h.services != nil && h.services.VM != nil {
				from := parseAddress(callObj.From)
				to := parseAddress(callObj.To)
				input := strings.TrimPrefix(callObj.Data, "0x")
				data, _ := hex.DecodeString(input)
				estimated, estErr := h.services.VM.EstimateGas(from, to, data)
				if estErr != nil {
					result = "0x5208"
				} else {
					result = fmt.Sprintf("0x%x", estimated)
				}
			} else {
				result = "0x5208"
			}
		}

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

// DefaultGasLimit is the default gas for eth_call / eth_estimateGas.
const DefaultGasLimit uint64 = 30_000_000

// resolveBlockNumber parses a block number string (hex or "latest"/"earliest"/"pending").
func resolveBlockNumber(tag string, services *ServiceRegistry) uint64 {
	switch tag {
	case "latest", "pending", "":
		if services != nil && services.BlockHeight != nil {
			return services.BlockHeight()
		}
		return 0
	case "earliest":
		return 0
	default:
		tag = strings.TrimPrefix(tag, "0x")
		var n uint64
		fmt.Sscanf(tag, "%x", &n)
		return n
	}
}

// buildBlockResponse constructs a block JSON response for the given height.
func (h *Handlers) buildBlockResponse(height uint64) any {
	if h.services != nil && h.services.BlockStore != nil {
		blk, err := h.services.BlockStore.GetBlockByNumber(height)
		if err == nil && blk != nil {
			return formatBlock(blk)
		}
	}
	// Fallback: minimal block with correct height
	return map[string]any{
		"number":       fmt.Sprintf("0x%x", height),
		"hash":         "0x" + "0000000000000000000000000000000000000000000000000000000000000000",
		"parentHash":   "0x" + "0000000000000000000000000000000000000000000000000000000000000000",
		"timestamp":    "0x0",
		"gasLimit":     "0x1c9c380",
		"gasUsed":      "0x0",
		"miner":        "0x" + "0000000000000000000000000000000000000000",
		"transactions": []any{},
	}
}

// formatBlock converts a BlockData into a JSON-RPC compatible map.
func formatBlock(blk *BlockData) map[string]any {
	txs := make([]string, len(blk.Transactions))
	for i, tx := range blk.Transactions {
		txs[i] = "0x" + hex.EncodeToString(tx)
	}
	return map[string]any{
		"number":       fmt.Sprintf("0x%x", blk.Number),
		"hash":         "0x" + hex.EncodeToString(blk.Hash[:]),
		"parentHash":   "0x" + hex.EncodeToString(blk.ParentHash[:]),
		"timestamp":    fmt.Sprintf("0x%x", blk.Timestamp),
		"gasLimit":     fmt.Sprintf("0x%x", blk.GasLimit),
		"gasUsed":      fmt.Sprintf("0x%x", blk.GasUsed),
		"miner":        "0x" + hex.EncodeToString(blk.Miner[:]),
		"transactions": txs,
	}
}

// parseAddress decodes a hex-encoded Ethereum address (0x-prefixed) into [20]byte.
func parseAddress(s string) [20]byte {
	s = strings.TrimPrefix(s, "0x")
	var addr [20]byte
	b, _ := hex.DecodeString(s)
	if len(b) > 20 {
		b = b[len(b)-20:]
	}
	copy(addr[20-len(b):], b)
	return addr
}

// parseHash decodes a hex-encoded 32-byte hash (0x-prefixed) into [32]byte.
func parseHash(s string) [32]byte {
	s = strings.TrimPrefix(s, "0x")
	var h [32]byte
	b, _ := hex.DecodeString(s)
	if len(b) > 32 {
		b = b[len(b)-32:]
	}
	copy(h[32-len(b):], b)
	return h
}
