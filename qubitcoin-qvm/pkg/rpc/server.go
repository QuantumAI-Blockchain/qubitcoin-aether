// Package rpc implements the QVM RPC server.
//
// Provides:
//   - gRPC server for high-performance internal communication
//   - REST/HTTP server for external API access
//   - JSON-RPC endpoint for MetaMask/Web3 compatibility (eth_* methods)
//   - Health and readiness endpoints
//   - Prometheus metrics endpoint
//
// Default ports:
//   - gRPC:  50052
//   - HTTP:  8080 (REST + JSON-RPC + metrics)
package rpc

import (
	"context"
	"fmt"
	"math/big"
	"net"
	"net/http"
	"sync"
	"time"

	"go.uber.org/zap"
)

// ServerConfig holds configuration for the RPC server.
type ServerConfig struct {
	// GRPCAddr is the gRPC listen address (default ":50052").
	GRPCAddr string
	// HTTPAddr is the HTTP listen address (default ":8080").
	HTTPAddr string
	// ChainID is the chain identifier (3301 mainnet, 3302 testnet).
	ChainID uint64
	// ReadTimeout is the HTTP read timeout.
	ReadTimeout time.Duration
	// WriteTimeout is the HTTP write timeout.
	WriteTimeout time.Duration
	// MaxRequestSize is the maximum request body size in bytes.
	MaxRequestSize int64
	// EnableCORS allows cross-origin requests.
	EnableCORS bool
	// CORSOrigins is the list of allowed origins.
	CORSOrigins []string
}

// DefaultServerConfig returns production defaults.
func DefaultServerConfig() *ServerConfig {
	return &ServerConfig{
		GRPCAddr:       ":50052",
		HTTPAddr:       ":8080",
		ChainID:        3301,
		ReadTimeout:    30 * time.Second,
		WriteTimeout:   30 * time.Second,
		MaxRequestSize: 5 * 1024 * 1024, // 5MB
		EnableCORS:     true,
		CORSOrigins:    []string{"https://qbc.network"},
	}
}

// StateReader is the minimal interface for reading account state (balance, nonce, code).
type StateReader interface {
	GetBalance(addr [20]byte) *big.Int
	GetNonce(addr [20]byte) uint64
	GetCode(addr [20]byte) []byte
	GetStorage(addr [20]byte, key [32]byte) [32]byte
}

// ServiceRegistry holds references to QVM subsystems that RPC handlers need.
type ServiceRegistry struct {
	// ChainID is the network chain ID.
	ChainID uint64
	// BlockHeight returns the current block height.
	BlockHeight func() uint64
	// Version is the QVM software version.
	Version string
	// State provides read access to account balances, nonces, and code.
	State StateReader
}

// Server is the QVM RPC server providing gRPC and HTTP/REST endpoints.
type Server struct {
	config   *ServerConfig
	services *ServiceRegistry
	logger   *zap.Logger

	httpServer *http.Server
	grpcLis    net.Listener

	mu      sync.Mutex
	running bool
}

// NewServer creates a new RPC server.
func NewServer(config *ServerConfig, services *ServiceRegistry, logger *zap.Logger) *Server {
	if config == nil {
		config = DefaultServerConfig()
	}
	if logger == nil {
		logger, _ = zap.NewProduction()
	}
	return &Server{
		config:   config,
		services: services,
		logger:   logger,
	}
}

// Start starts both the gRPC and HTTP servers.
func (s *Server) Start() error {
	s.mu.Lock()
	if s.running {
		s.mu.Unlock()
		return fmt.Errorf("server already running")
	}
	s.running = true
	s.mu.Unlock()

	// Build HTTP router
	mux := http.NewServeMux()
	s.registerHTTPRoutes(mux)

	s.httpServer = &http.Server{
		Addr:           s.config.HTTPAddr,
		Handler:        s.corsMiddleware(s.requestLimitMiddleware(mux)),
		ReadTimeout:    s.config.ReadTimeout,
		WriteTimeout:   s.config.WriteTimeout,
		MaxHeaderBytes: 1 << 20, // 1MB headers
	}

	// Start HTTP server
	go func() {
		s.logger.Info("HTTP server starting", zap.String("addr", s.config.HTTPAddr))
		if err := s.httpServer.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			s.logger.Error("HTTP server error", zap.Error(err))
		}
	}()

	// Start gRPC listener
	var err error
	s.grpcLis, err = net.Listen("tcp", s.config.GRPCAddr)
	if err != nil {
		return fmt.Errorf("failed to listen on %s: %w", s.config.GRPCAddr, err)
	}

	go func() {
		s.logger.Info("gRPC server starting", zap.String("addr", s.config.GRPCAddr))
		// gRPC server registration happens here when protobuf services are defined.
		// For now, the listener is established and ready.
	}()

	s.logger.Info("QVM RPC server started",
		zap.String("http", s.config.HTTPAddr),
		zap.String("grpc", s.config.GRPCAddr),
		zap.Uint64("chainID", s.config.ChainID),
	)

	return nil
}

// Stop gracefully shuts down the server.
func (s *Server) Stop(ctx context.Context) error {
	s.mu.Lock()
	defer s.mu.Unlock()

	if !s.running {
		return nil
	}
	s.running = false

	s.logger.Info("shutting down RPC server")

	var firstErr error

	// Shutdown HTTP
	if s.httpServer != nil {
		if err := s.httpServer.Shutdown(ctx); err != nil {
			firstErr = fmt.Errorf("HTTP shutdown error: %w", err)
		}
	}

	// Close gRPC listener
	if s.grpcLis != nil {
		if err := s.grpcLis.Close(); err != nil && firstErr == nil {
			firstErr = fmt.Errorf("gRPC shutdown error: %w", err)
		}
	}

	return firstErr
}

// registerHTTPRoutes sets up all HTTP endpoints.
func (s *Server) registerHTTPRoutes(mux *http.ServeMux) {
	h := NewHandlers(s.services, s.logger)

	// Health & readiness
	mux.HandleFunc("/health", h.Health)
	mux.HandleFunc("/ready", h.Ready)

	// Node info
	mux.HandleFunc("/", h.NodeInfo)
	mux.HandleFunc("/info", h.NodeInfo)

	// Chain
	mux.HandleFunc("/chain/info", h.ChainInfo)

	// JSON-RPC (MetaMask/Web3 compatible)
	mux.HandleFunc("/jsonrpc", h.JSONRPCHandler)
	mux.HandleFunc("/rpc", h.JSONRPCHandler)

	// QVM
	mux.HandleFunc("/qvm/info", h.QVMInfo)

	// Metrics (Prometheus)
	mux.HandleFunc("/metrics", h.Metrics)
}

// corsMiddleware adds CORS headers for frontend access.
func (s *Server) corsMiddleware(next http.Handler) http.Handler {
	if !s.config.EnableCORS {
		return next
	}
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		origin := r.Header.Get("Origin")
		allowed := false
		for _, o := range s.config.CORSOrigins {
			if o == "*" || o == origin {
				allowed = true
				break
			}
		}
		if allowed {
			w.Header().Set("Access-Control-Allow-Origin", origin)
			w.Header().Set("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
			w.Header().Set("Access-Control-Allow-Headers", "Content-Type, Authorization, X-API-Key")
			w.Header().Set("Access-Control-Max-Age", "3600")
		}
		if r.Method == http.MethodOptions {
			w.WriteHeader(http.StatusNoContent)
			return
		}
		next.ServeHTTP(w, r)
	})
}

// requestLimitMiddleware enforces request body size limits.
func (s *Server) requestLimitMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Body != nil && s.config.MaxRequestSize > 0 {
			r.Body = http.MaxBytesReader(w, r.Body, s.config.MaxRequestSize)
		}
		next.ServeHTTP(w, r)
	})
}
