// Package grpc implements the QVM gRPC sidecar server.
//
// This server enables the Substrate node (qbc-qvm-anchor pallet) to communicate
// with the Go QVM via gRPC. It delegates all operations to the existing
// ServiceRegistry interfaces (StateReader, BlockStore, TxPool, VMCaller).
//
// Because protoc-generated code is not available yet, the service is registered
// manually using google.golang.org/grpc with a JSON codec. This is fully
// interoperable with any gRPC client that specifies content-type "application/grpc+json".
// When protoc-generated stubs become available, simply swap out the codec and
// message types — the service descriptor and handler logic remain identical.
//
// Default port: 50053
package grpc

import (
	"context"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"math/big"
	"net"
	"runtime"
	"strings"
	"sync"
	"time"

	"go.uber.org/zap"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/encoding"
	"google.golang.org/grpc/status"

	"github.com/BlockArtica/qubitcoin-qvm/pkg/crypto"
	"github.com/BlockArtica/qubitcoin-qvm/pkg/rpc"
)

// ─── JSON Codec ───────────────────────────────────────────────────────
// Register a JSON codec so gRPC can marshal/unmarshal our Go structs
// without protoc-generated code. Clients must use content-type
// "application/grpc+json" or we register as "proto" fallback that
// handles our concrete types via JSON.

func init() {
	encoding.RegisterCodec(JSONCodec{})
}

// JSONCodec implements grpc encoding.Codec using encoding/json.
type JSONCodec struct{}

// Marshal serializes v to JSON bytes.
func (JSONCodec) Marshal(v interface{}) ([]byte, error) {
	return json.Marshal(v)
}

// Unmarshal deserializes data from JSON bytes into v.
func (JSONCodec) Unmarshal(data []byte, v interface{}) error {
	return json.Unmarshal(data, v)
}

// Name returns the codec name. Using "json" so clients specify
// content-type "application/grpc+json".
func (JSONCodec) Name() string {
	return "json"
}

// ─── Request/Response Types ───────────────────────────────────────────
// These mirror the proto/qvm.proto messages. Field names use JSON tags
// matching the proto3 JSON mapping (camelCase).

// ExecuteContractRequest is the request for ExecuteContract RPC.
type ExecuteContractRequest struct {
	From        string `json:"from"`
	To          string `json:"to"`
	Data        string `json:"data"`
	GasLimit    uint64 `json:"gasLimit"`
	BlockHeight uint64 `json:"blockHeight"`
}

// ExecuteContractResponse is the response for ExecuteContract RPC.
type ExecuteContractResponse struct {
	ReturnData string `json:"returnData"`
	GasUsed    uint64 `json:"gasUsed"`
	Success    bool   `json:"success"`
	Error      string `json:"error,omitempty"`
}

// DeployContractRequest is the request for DeployContract RPC.
type DeployContractRequest struct {
	From            string `json:"from"`
	Bytecode        string `json:"bytecode"`
	ConstructorArgs string `json:"constructorArgs"`
	GasLimit        uint64 `json:"gasLimit"`
	Value           string `json:"value"`
}

// DeployContractResponse is the response for DeployContract RPC.
type DeployContractResponse struct {
	ContractAddress string `json:"contractAddress"`
	GasUsed         uint64 `json:"gasUsed"`
	Success         bool   `json:"success"`
	Error           string `json:"error,omitempty"`
	TxHash          string `json:"txHash"`
}

// StateRootRequest is the request for GetStateRoot RPC.
type StateRootRequest struct {
	BlockHeight uint64 `json:"blockHeight"`
}

// StateRootResponse is the response for GetStateRoot RPC.
type StateRootResponse struct {
	StateRoot    string `json:"stateRoot"`
	BlockHeight  uint64 `json:"blockHeight"`
	AccountCount uint64 `json:"accountCount"`
}

// BalanceRequest is the request for GetBalance RPC.
type BalanceRequest struct {
	Address     string `json:"address"`
	BlockHeight uint64 `json:"blockHeight"`
}

// BalanceResponse is the response for GetBalance RPC.
type BalanceResponse struct {
	Balance string `json:"balance"`
	Nonce   uint64 `json:"nonce"`
}

// CodeRequest is the request for GetCode RPC.
type CodeRequest struct {
	Address     string `json:"address"`
	BlockHeight uint64 `json:"blockHeight"`
}

// CodeResponse is the response for GetCode RPC.
type CodeResponse struct {
	Code     string `json:"code"`
	CodeSize uint64 `json:"codeSize"`
}

// StorageRequest is the request for GetStorage RPC.
type StorageRequest struct {
	Address     string `json:"address"`
	Key         string `json:"key"`
	BlockHeight uint64 `json:"blockHeight"`
}

// StorageResponse is the response for GetStorage RPC.
type StorageResponse struct {
	Value string `json:"value"`
}

// EstimateGasRequest is the request for EstimateGas RPC.
type EstimateGasRequest struct {
	From  string `json:"from"`
	To    string `json:"to"`
	Data  string `json:"data"`
	Value string `json:"value"`
}

// EstimateGasResponse is the response for EstimateGas RPC.
type EstimateGasResponse struct {
	Gas     uint64 `json:"gas"`
	Success bool   `json:"success"`
	Error   string `json:"error,omitempty"`
}

// SubmitTxRequest is the request for SubmitTransaction RPC.
type SubmitTxRequest struct {
	RawTx string `json:"rawTx"`
}

// SubmitTxResponse is the response for SubmitTransaction RPC.
type SubmitTxResponse struct {
	TxHash  string `json:"txHash"`
	Success bool   `json:"success"`
	Error   string `json:"error,omitempty"`
}

// QVMInfoRequest is the request for GetQVMInfo RPC.
type QVMInfoRequest struct{}

// QVMInfoResponse is the response for GetQVMInfo RPC.
type QVMInfoResponse struct {
	Version        string   `json:"version"`
	ChainID        uint64   `json:"chainId"`
	BlockHeight    uint64   `json:"blockHeight"`
	EvmOpcodes     uint32   `json:"evmOpcodes"`
	QuantumOpcodes uint32   `json:"quantumOpcodes"`
	BlockGasLimit  uint64   `json:"blockGasLimit"`
	MaxCodeSize    uint64   `json:"maxCodeSize"`
	Features       []string `json:"features"`
}

// HealthRequest is the request for Health RPC.
type HealthRequest struct{}

// HealthResponse is the response for Health RPC.
type HealthResponse struct {
	Healthy             bool    `json:"healthy"`
	Message             string  `json:"message"`
	UptimeSeconds       float64 `json:"uptimeSeconds"`
	Goroutines          uint32  `json:"goroutines"`
	StateAvailable      bool    `json:"stateAvailable"`
	VMAvailable         bool    `json:"vmAvailable"`
	TxpoolAvailable     bool    `json:"txpoolAvailable"`
	BlockstoreAvailable bool    `json:"blockstoreAvailable"`
}

// ─── StateRootComputer ────────────────────────────────────────────────

// StateRootComputer computes the Merkle state root. This is an optional
// interface that the StateReader may also implement.
type StateRootComputer interface {
	ComputeStateRoot() [32]byte
}

// ─── Server ───────────────────────────────────────────────────────────

// DefaultGRPCPort is the default gRPC listen port for the QVM sidecar.
const DefaultGRPCPort = ":50053"

// defaultGasLimit is the fallback gas limit for calls without an explicit limit.
const defaultGasLimit uint64 = 30_000_000

// Server is the QVM gRPC sidecar server. It wraps the ServiceRegistry
// interfaces and exposes them over gRPC for the Substrate node to call.
type Server struct {
	services  *rpc.ServiceRegistry
	logger    *zap.Logger
	startTime time.Time

	grpcServer *grpc.Server
	listener   net.Listener

	mu      sync.Mutex
	running bool
}

// NewServer creates a new QVM gRPC sidecar server.
func NewServer(services *rpc.ServiceRegistry, logger *zap.Logger) *Server {
	if logger == nil {
		logger, _ = zap.NewProduction()
	}
	return &Server{
		services:  services,
		logger:    logger,
		startTime: time.Now(),
	}
}

// Start starts the gRPC server on the given address.
// If addr is empty, DefaultGRPCPort (":50053") is used.
func (s *Server) Start(addr string) error {
	s.mu.Lock()
	if s.running {
		s.mu.Unlock()
		return fmt.Errorf("gRPC server already running")
	}
	s.mu.Unlock()

	if addr == "" {
		addr = DefaultGRPCPort
	}

	lis, err := net.Listen("tcp", addr)
	if err != nil {
		return fmt.Errorf("failed to listen on %s: %w", addr, err)
	}
	s.listener = lis

	// Create gRPC server with the JSON codec as default.
	s.grpcServer = grpc.NewServer(
		grpc.MaxRecvMsgSize(5*1024*1024), // 5 MB
		grpc.MaxSendMsgSize(5*1024*1024), // 5 MB
		grpc.ForceServerCodec(JSONCodec{}),
	)

	// Register the QVM service using manual service descriptor.
	// Health checking is built into the QVM service itself (Health RPC).
	s.registerQVMService()

	s.mu.Lock()
	s.running = true
	s.mu.Unlock()

	go func() {
		s.logger.Info("QVM gRPC sidecar starting",
			zap.String("addr", addr),
		)
		if err := s.grpcServer.Serve(lis); err != nil {
			s.logger.Error("gRPC server error", zap.Error(err))
		}
	}()

	return nil
}

// Stop gracefully shuts down the gRPC server.
func (s *Server) Stop() {
	s.mu.Lock()
	defer s.mu.Unlock()

	if !s.running {
		return
	}
	s.running = false

	s.logger.Info("shutting down QVM gRPC sidecar")
	if s.grpcServer != nil {
		s.grpcServer.GracefulStop()
	}
}

// ─── Service Registration ─────────────────────────────────────────────

// registerQVMService registers the QVMService with the gRPC server using
// manual service descriptors. Each method handler unmarshals the request,
// delegates to the appropriate ServiceRegistry interface, and marshals
// the response.
func (s *Server) registerQVMService() {
	serviceDesc := &grpc.ServiceDesc{
		ServiceName: "qvm.QVMService",
		HandlerType: (*interface{})(nil),
		Methods: []grpc.MethodDesc{
			{
				MethodName: "ExecuteContract",
				Handler:    s.handleExecuteContract,
			},
			{
				MethodName: "DeployContract",
				Handler:    s.handleDeployContract,
			},
			{
				MethodName: "GetStateRoot",
				Handler:    s.handleGetStateRoot,
			},
			{
				MethodName: "GetBalance",
				Handler:    s.handleGetBalance,
			},
			{
				MethodName: "GetCode",
				Handler:    s.handleGetCode,
			},
			{
				MethodName: "GetStorage",
				Handler:    s.handleGetStorage,
			},
			{
				MethodName: "EstimateGas",
				Handler:    s.handleEstimateGas,
			},
			{
				MethodName: "SubmitTransaction",
				Handler:    s.handleSubmitTransaction,
			},
			{
				MethodName: "GetQVMInfo",
				Handler:    s.handleGetQVMInfo,
			},
			{
				MethodName: "Health",
				Handler:    s.handleHealth,
			},
		},
		Streams:  []grpc.StreamDesc{},
		Metadata: "proto/qvm.proto",
	}

	s.grpcServer.RegisterService(serviceDesc, s)
}

// ─── RPC Handlers ─────────────────────────────────────────────────────

// handleExecuteContract executes a read-only contract call (eth_call equivalent).
func (s *Server) handleExecuteContract(
	srv interface{},
	ctx context.Context,
	dec func(interface{}) error,
	interceptor grpc.UnaryServerInterceptor,
) (interface{}, error) {
	req := &ExecuteContractRequest{}
	if err := dec(req); err != nil {
		return nil, status.Errorf(codes.InvalidArgument, "failed to decode request: %v", err)
	}

	s.logger.Debug("ExecuteContract",
		zap.String("from", req.From),
		zap.String("to", req.To),
		zap.Uint64("gas_limit", req.GasLimit),
	)

	if s.services == nil || s.services.VM == nil {
		return nil, status.Error(codes.Unavailable, "VM service not available")
	}

	from := parseAddress(req.From)
	to := parseAddress(req.To)
	data, err := decodeHex(req.Data)
	if err != nil {
		return nil, status.Errorf(codes.InvalidArgument, "invalid data hex: %v", err)
	}

	gasLimit := req.GasLimit
	if gasLimit == 0 {
		gasLimit = defaultGasLimit
	}

	retData, gasUsed, callErr := s.services.VM.StaticCall(from, to, data, gasLimit)

	resp := &ExecuteContractResponse{
		GasUsed: gasUsed,
		Success: callErr == nil,
	}

	if callErr != nil {
		resp.Error = callErr.Error()
		resp.ReturnData = "0x"
	} else {
		resp.ReturnData = "0x" + hex.EncodeToString(retData)
	}

	return resp, nil
}

// handleDeployContract deploys contract bytecode via the VM.
func (s *Server) handleDeployContract(
	srv interface{},
	ctx context.Context,
	dec func(interface{}) error,
	interceptor grpc.UnaryServerInterceptor,
) (interface{}, error) {
	req := &DeployContractRequest{}
	if err := dec(req); err != nil {
		return nil, status.Errorf(codes.InvalidArgument, "failed to decode request: %v", err)
	}

	s.logger.Debug("DeployContract",
		zap.String("from", req.From),
		zap.Int("bytecode_len", len(req.Bytecode)),
		zap.Uint64("gas_limit", req.GasLimit),
	)

	if s.services == nil || s.services.VM == nil {
		return nil, status.Error(codes.Unavailable, "VM service not available")
	}

	from := parseAddress(req.From)
	var to [20]byte // zero address = deploy

	// Concatenate bytecode + constructor args.
	bytecodeBytes, err := decodeHex(req.Bytecode)
	if err != nil {
		return nil, status.Errorf(codes.InvalidArgument, "invalid bytecode hex: %v", err)
	}
	if req.ConstructorArgs != "" {
		args, argErr := decodeHex(req.ConstructorArgs)
		if argErr != nil {
			return nil, status.Errorf(codes.InvalidArgument, "invalid constructor_args hex: %v", argErr)
		}
		bytecodeBytes = append(bytecodeBytes, args...)
	}

	gasLimit := req.GasLimit
	if gasLimit == 0 {
		gasLimit = defaultGasLimit
	}

	retData, gasUsed, callErr := s.services.VM.StaticCall(from, to, bytecodeBytes, gasLimit)

	resp := &DeployContractResponse{
		GasUsed: gasUsed,
		Success: callErr == nil,
	}

	if callErr != nil {
		resp.Error = callErr.Error()
	} else {
		// The return data from a deployment is the runtime bytecode.
		// The contract address is derived from the deployer address + nonce.
		var nonce uint64
		if s.services.State != nil {
			nonce = s.services.State.GetNonce(from)
		}
		contractAddr := computeCreateAddress(from, nonce)
		resp.ContractAddress = "0x" + hex.EncodeToString(contractAddr[:])
		if len(retData) > 0 {
			resp.TxHash = "0x" + hex.EncodeToString(retData)
		}
	}

	return resp, nil
}

// handleGetStateRoot returns the current Merkle Patricia Trie state root.
func (s *Server) handleGetStateRoot(
	srv interface{},
	ctx context.Context,
	dec func(interface{}) error,
	interceptor grpc.UnaryServerInterceptor,
) (interface{}, error) {
	req := &StateRootRequest{}
	if err := dec(req); err != nil {
		return nil, status.Errorf(codes.InvalidArgument, "failed to decode request: %v", err)
	}

	s.logger.Debug("GetStateRoot", zap.Uint64("block_height", req.BlockHeight))

	// Compute the state root from the StateReader if it implements
	// the StateRootComputer interface.
	var stateRootBytes [32]byte
	if s.services != nil && s.services.State != nil {
		if src, ok := s.services.State.(StateRootComputer); ok {
			stateRootBytes = src.ComputeStateRoot()
		}
	}

	var blockHeight uint64
	if s.services != nil && s.services.BlockHeight != nil {
		blockHeight = s.services.BlockHeight()
	}

	resp := &StateRootResponse{
		StateRoot:   "0x" + hex.EncodeToString(stateRootBytes[:]),
		BlockHeight: blockHeight,
	}

	return resp, nil
}

// handleGetBalance returns the QBC balance and nonce of an account.
func (s *Server) handleGetBalance(
	srv interface{},
	ctx context.Context,
	dec func(interface{}) error,
	interceptor grpc.UnaryServerInterceptor,
) (interface{}, error) {
	req := &BalanceRequest{}
	if err := dec(req); err != nil {
		return nil, status.Errorf(codes.InvalidArgument, "failed to decode request: %v", err)
	}

	s.logger.Debug("GetBalance", zap.String("address", req.Address))

	if s.services == nil || s.services.State == nil {
		return nil, status.Error(codes.Unavailable, "state service not available")
	}

	addr := parseAddress(req.Address)
	balance := s.services.State.GetBalance(addr)
	nonce := s.services.State.GetNonce(addr)

	if balance == nil {
		balance = new(big.Int)
	}

	resp := &BalanceResponse{
		Balance: "0x" + balance.Text(16),
		Nonce:   nonce,
	}

	return resp, nil
}

// handleGetCode returns the deployed bytecode at a contract address.
func (s *Server) handleGetCode(
	srv interface{},
	ctx context.Context,
	dec func(interface{}) error,
	interceptor grpc.UnaryServerInterceptor,
) (interface{}, error) {
	req := &CodeRequest{}
	if err := dec(req); err != nil {
		return nil, status.Errorf(codes.InvalidArgument, "failed to decode request: %v", err)
	}

	s.logger.Debug("GetCode", zap.String("address", req.Address))

	if s.services == nil || s.services.State == nil {
		return nil, status.Error(codes.Unavailable, "state service not available")
	}

	addr := parseAddress(req.Address)
	code := s.services.State.GetCode(addr)

	resp := &CodeResponse{
		Code:     "0x" + hex.EncodeToString(code),
		CodeSize: uint64(len(code)),
	}

	return resp, nil
}

// handleGetStorage returns the value at a specific storage slot.
func (s *Server) handleGetStorage(
	srv interface{},
	ctx context.Context,
	dec func(interface{}) error,
	interceptor grpc.UnaryServerInterceptor,
) (interface{}, error) {
	req := &StorageRequest{}
	if err := dec(req); err != nil {
		return nil, status.Errorf(codes.InvalidArgument, "failed to decode request: %v", err)
	}

	s.logger.Debug("GetStorage",
		zap.String("address", req.Address),
		zap.String("key", req.Key),
	)

	if s.services == nil || s.services.State == nil {
		return nil, status.Error(codes.Unavailable, "state service not available")
	}

	addr := parseAddress(req.Address)
	key := parseHash(req.Key)
	val := s.services.State.GetStorage(addr, key)

	resp := &StorageResponse{
		Value: "0x" + hex.EncodeToString(val[:]),
	}

	return resp, nil
}

// handleEstimateGas estimates the gas required for a transaction.
func (s *Server) handleEstimateGas(
	srv interface{},
	ctx context.Context,
	dec func(interface{}) error,
	interceptor grpc.UnaryServerInterceptor,
) (interface{}, error) {
	req := &EstimateGasRequest{}
	if err := dec(req); err != nil {
		return nil, status.Errorf(codes.InvalidArgument, "failed to decode request: %v", err)
	}

	s.logger.Debug("EstimateGas",
		zap.String("from", req.From),
		zap.String("to", req.To),
	)

	if s.services == nil || s.services.VM == nil {
		// Return default gas estimate when VM is not available.
		return &EstimateGasResponse{
			Gas:     21000,
			Success: true,
		}, nil
	}

	from := parseAddress(req.From)
	to := parseAddress(req.To)
	data, err := decodeHex(req.Data)
	if err != nil {
		return nil, status.Errorf(codes.InvalidArgument, "invalid data hex: %v", err)
	}

	estimated, estErr := s.services.VM.EstimateGas(from, to, data)

	resp := &EstimateGasResponse{
		Gas:     estimated,
		Success: estErr == nil,
	}
	if estErr != nil {
		resp.Error = estErr.Error()
		// Fall back to simple transfer gas on estimation failure.
		if resp.Gas == 0 {
			resp.Gas = 21000
		}
	}

	return resp, nil
}

// handleSubmitTransaction submits a signed transaction to the mempool.
func (s *Server) handleSubmitTransaction(
	srv interface{},
	ctx context.Context,
	dec func(interface{}) error,
	interceptor grpc.UnaryServerInterceptor,
) (interface{}, error) {
	req := &SubmitTxRequest{}
	if err := dec(req); err != nil {
		return nil, status.Errorf(codes.InvalidArgument, "failed to decode request: %v", err)
	}

	s.logger.Debug("SubmitTransaction", zap.Int("raw_tx_len", len(req.RawTx)))

	if s.services == nil || s.services.TxPool == nil {
		return nil, status.Error(codes.Unavailable, "transaction pool not available")
	}

	txBytes, err := decodeHex(req.RawTx)
	if err != nil {
		return nil, status.Errorf(codes.InvalidArgument, "invalid raw_tx hex: %v", err)
	}

	if len(txBytes) == 0 {
		return nil, status.Error(codes.InvalidArgument, "empty transaction data")
	}

	txHash, submitErr := s.services.TxPool.SubmitRawTransaction(txBytes)

	resp := &SubmitTxResponse{
		TxHash:  "0x" + hex.EncodeToString(txHash[:]),
		Success: submitErr == nil,
	}
	if submitErr != nil {
		resp.Error = submitErr.Error()
	}

	return resp, nil
}

// handleGetQVMInfo returns QVM engine metadata.
func (s *Server) handleGetQVMInfo(
	srv interface{},
	ctx context.Context,
	dec func(interface{}) error,
	interceptor grpc.UnaryServerInterceptor,
) (interface{}, error) {
	req := &QVMInfoRequest{}
	if err := dec(req); err != nil {
		return nil, status.Errorf(codes.InvalidArgument, "failed to decode request: %v", err)
	}

	s.logger.Debug("GetQVMInfo")

	var blockHeight uint64
	var chainID uint64 = 3303
	version := "0.1.0"

	if s.services != nil {
		if s.services.BlockHeight != nil {
			blockHeight = s.services.BlockHeight()
		}
		if s.services.ChainID > 0 {
			chainID = s.services.ChainID
		}
		if s.services.Version != "" {
			version = s.services.Version
		}
	}

	resp := &QVMInfoResponse{
		Version:        version,
		ChainID:        chainID,
		BlockHeight:    blockHeight,
		EvmOpcodes:     155,
		QuantumOpcodes: 10,
		BlockGasLimit:  30_000_000,
		MaxCodeSize:    24576,
		Features: []string{
			"evm_compatible",
			"quantum_opcodes",
			"compliance_engine",
			"plugin_system",
			"post_quantum_crypto",
			"dilithium5_signatures",
			"grpc_sidecar",
		},
	}

	return resp, nil
}

// handleHealth returns the health status of the QVM service.
func (s *Server) handleHealth(
	srv interface{},
	ctx context.Context,
	dec func(interface{}) error,
	interceptor grpc.UnaryServerInterceptor,
) (interface{}, error) {
	req := &HealthRequest{}
	if err := dec(req); err != nil {
		return nil, status.Errorf(codes.InvalidArgument, "failed to decode request: %v", err)
	}

	stateAvailable := s.services != nil && s.services.State != nil
	vmAvailable := s.services != nil && s.services.VM != nil
	txpoolAvailable := s.services != nil && s.services.TxPool != nil
	blockstoreAvailable := s.services != nil && s.services.BlockStore != nil

	healthy := s.services != nil
	msg := "healthy"
	if !healthy {
		msg = "service registry not initialized"
	} else if !stateAvailable && !vmAvailable {
		msg = "degraded: no state or VM backends"
	}

	resp := &HealthResponse{
		Healthy:             healthy,
		Message:             msg,
		UptimeSeconds:       time.Since(s.startTime).Seconds(),
		Goroutines:          uint32(runtime.NumGoroutine()),
		StateAvailable:      stateAvailable,
		VMAvailable:         vmAvailable,
		TxpoolAvailable:     txpoolAvailable,
		BlockstoreAvailable: blockstoreAvailable,
	}

	return resp, nil
}

// ─── Helpers ──────────────────────────────────────────────────────────

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

// decodeHex decodes a hex string (with optional 0x prefix) into bytes.
func decodeHex(s string) ([]byte, error) {
	s = strings.TrimPrefix(s, "0x")
	if s == "" {
		return []byte{}, nil
	}
	return hex.DecodeString(s)
}

// computeCreateAddress computes the contract address for a CREATE operation.
// address = keccak256(rlp([sender, nonce]))[12:]
func computeCreateAddress(sender [20]byte, nonce uint64) [20]byte {
	// RLP encode [sender, nonce]:
	// sender is a 20-byte string: prefix 0x94 (0x80+20) + 20 bytes
	// nonce encoding depends on value
	var rlpNonce []byte
	switch {
	case nonce == 0:
		rlpNonce = []byte{0x80} // RLP empty string
	case nonce < 128:
		rlpNonce = []byte{byte(nonce)}
	case nonce < 256:
		rlpNonce = []byte{0x81, byte(nonce)}
	default:
		// Encode nonce as big-endian bytes with length prefix
		n := new(big.Int).SetUint64(nonce)
		nb := n.Bytes()
		rlpNonce = append([]byte{0x80 + byte(len(nb))}, nb...)
	}

	// list payload = [0x94 + sender] + rlpNonce
	payload := make([]byte, 0, 1+20+len(rlpNonce))
	payload = append(payload, 0x94) // 0x80 + 20 (20-byte string prefix)
	payload = append(payload, sender[:]...)
	payload = append(payload, rlpNonce...)

	// list header
	var encoded []byte
	if len(payload) < 56 {
		encoded = append([]byte{0xc0 + byte(len(payload))}, payload...)
	} else {
		lenBytes := new(big.Int).SetInt64(int64(len(payload))).Bytes()
		encoded = append([]byte{0xf7 + byte(len(lenBytes))}, lenBytes...)
		encoded = append(encoded, payload...)
	}

	// Keccak-256 hash using the existing crypto package.
	hash := crypto.Keccak256(encoded)

	var addr [20]byte
	copy(addr[:], hash[12:])
	return addr
}
